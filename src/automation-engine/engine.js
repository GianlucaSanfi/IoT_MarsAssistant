const amqp = require('amqplib');
const { Pool } = require('pg');

// ─── Config ───────────────────────────────────────────────────────────────
const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://rabbitmq';
const RULES_REFRESH_MS = parseInt(process.env.RULES_REFRESH_MS || '5000');

const db = new Pool({
  host: process.env.DB_HOST || 'postgres',
  port: 5432,
  user: process.env.DB_USER || 'iot',
  password: process.env.DB_PASSWORD || 'iot',
  database: process.env.DB_NAME || 'iotdb',
});

// ─── In-memory rule cache ─────────────────────────────────────────────────
let rules = [];
let rulesLastLoaded = 0;

async function loadRules() {
  try {
    const result = await db.query('SELECT * FROM rules WHERE enabled = true');
    rules = result.rows;
    rulesLastLoaded = Date.now();
    console.log(`[RULES] Loaded ${rules.length} active rules from database`);
  } catch (err) {
    console.error('[RULES] Failed to load rules:', err.message);
  }
}

// Refresh rules periodically
async function startRulesRefresh() {
  await loadRules();
  setInterval(loadRules, RULES_REFRESH_MS);
}

// ─── Rule Evaluation ──────────────────────────────────────────────────────
function evaluateRule(rule, sensorId, attribute, value) {
  if (rule.sensor !== sensorId) return false;
  if (rule.attribute !== attribute) return false;

  const threshold = parseFloat(rule.threshold);
  const v = parseFloat(value);

  if (isNaN(v) || isNaN(threshold)) return false;

  switch (rule.operator) {
    case '>':  return v > threshold;
    case '<':  return v < threshold;
    case '>=': return v >= threshold;
    case '<=': return v <= threshold;
    case '==': return v === threshold;
    case '!=': return v !== threshold;
    default:
      console.warn(`[EVAL] Unknown operator: ${rule.operator}`);
      return false;
  }
}

function checkRules(sensorId, attribute, value) {
  const triggered = [];
  for (const rule of rules) {
    if (rule.enabled === false) continue;
    if (evaluateRule(rule, sensorId, attribute, value)) {
      triggered.push(rule);
    }
  }
  return triggered;
}

// ─── Action Publisher ─────────────────────────────────────────────────────
async function publishAction(channel, rule, sensorId, attribute, sensorValue) {
  const exchange = 'actions';
  const now = new Date();
  const payload = {
    ruleId: rule.id,
    sensor: sensorId,
    attribute: attribute,
    sensorValue: sensorValue,
    actuator: rule.actuator,
    action: rule.action,
    triggeredAt: now.toISOString(),
    condition: `${rule.sensor}.${rule.attribute} ${rule.operator} ${rule.threshold}`,
  };

  try {
    channel.publish(
      exchange,
      rule.actuator,
      Buffer.from(JSON.stringify(payload)),
      { persistent: false, contentType: 'application/json' }
    );
    console.log(
      `[ACTION] Rule #${rule.id} triggered: ${rule.sensor}.${rule.attribute} ${rule.operator} ${rule.threshold} ` +
      `(got ${sensorValue}) → ${rule.actuator}: ${rule.action}`
    );
    // Update last_triggered in DB
    await db.query('UPDATE rules SET last_triggered = $1 WHERE id = $2', [now, rule.id]);
  } catch (err) {
    console.error('[ACTION] Failed to publish action:', err.message);
  }
}

// ─── RabbitMQ Consumer ────────────────────────────────────────────────────
async function startConsumer() {
  let retries = 15;

  while (retries > 0) {
    try {
      console.log('[AMQP] Connecting to RabbitMQ...');
      const conn = await amqp.connect(RABBITMQ_URL);

      conn.on('error', (err) => {
        console.error('[AMQP] Connection error:', err.message);
      });
      conn.on('close', () => {
        console.warn('[AMQP] Connection closed. Reconnecting in 5s...');
        setTimeout(startConsumer, 5000);
      });

      const channel = await conn.createChannel();
      channel.prefetch(10);

      // Sensor data exchange
      const sensorExchange = 'telemetry';
      await channel.assertExchange(sensorExchange, 'topic', { durable: true });

      // Actions exchange
      const actionsExchange = 'actions';
      await channel.assertExchange(actionsExchange, 'topic', { durable: false });

      // Durable queue bound to sensors.normalized
      const q = await channel.assertQueue('automation-engine', { exclusive: false, durable: true });
      await channel.bindQueue(q.queue, sensorExchange, 'sensors.normalized');

      console.log(`[AMQP] Connected. Consuming from exchange "${sensorExchange}" (sensors.normalized)`);

      channel.consume(q.queue, async (msg) => {
        if (msg === null) return;

        try {
          const data = JSON.parse(msg.content.toString());

          if (data.sensor_id === undefined || data.metric === undefined || data.value === undefined) {
            console.warn('[MSG] Skipping message with missing fields:', data);
            channel.ack(msg);
            return;
          }

          const triggered = checkRules(data.sensor_id, data.metric, data.value);
          for (const rule of triggered) {
            await publishAction(channel, rule, data.sensor_id, data.metric, data.value);
          }
        } catch (err) {
          console.error('[MSG] Failed to process message:', err.message);
        }

        channel.ack(msg);
      });

      return;

    } catch (err) {
      retries--;
      console.warn(`[AMQP] Not ready (${retries} retries left): ${err.message}`);
      await new Promise(r => setTimeout(r, 5000));
    }
  }

  console.error('[AMQP] Could not connect after all retries. Exiting.');
  process.exit(1);
}

// ─── Graceful shutdown ────────────────────────────────────────────────────
process.on('SIGTERM', async () => {
  console.log('[ENGINE] Shutting down...');
  await db.end();
  process.exit(0);
});

// ─── Main ─────────────────────────────────────────────────────────────────
(async () => {
  console.log('╔══════════════════════════════════╗');
  console.log('║     IoT Automation Engine        ║');
  console.log('╚══════════════════════════════════╝');

  await new Promise(r => setTimeout(r, 3000));

  await startRulesRefresh();
  await startConsumer();
})();