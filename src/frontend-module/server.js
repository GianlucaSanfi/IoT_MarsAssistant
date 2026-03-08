const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const amqp = require('amqplib');
const { Pool } = require('pg');
const path = require('path');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const db = new Pool({
  host: process.env.DB_HOST || 'postgres',
  port: 5432,
  user: process.env.DB_USER || 'iot',
  password: process.env.DB_PASSWORD || 'iot',
  database: process.env.DB_NAME || 'iotdb',
});

const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://rabbitmq';
const SIMULATOR_URL = process.env.API_BASE_URL || 'http://simulator:8080';

// ─── WebSocket broadcast ──────────────────────────────────────────────────
const clients = new Set();
const sensorCache = {}; // { sensor_id: { timestamp, sensor_id, metric, value, unit, status } }

wss.on('connection', (ws) => {
  clients.add(ws);
  // Send current sensor state to new client immediately
  if (Object.keys(sensorCache).length > 0) {
    Object.values(sensorCache).forEach(payload => {
      ws.send(JSON.stringify({ type: 'sensor_data', payload }));
    });
  }
  // Send current actuator state to new client
  ACTUATOR_IDS.forEach(id => {
    if (actuatorState[id]) {
      ws.send(JSON.stringify({ type: 'actuator_update', payload: { id, ...actuatorState[id] } }));
    }
  });
  ws.on('close', () => clients.delete(ws));
});

function broadcast(data) {
  const msg = JSON.stringify(data);
  for (const client of clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(msg);
    }
  }
}

// ─── RabbitMQ Consumer ────────────────────────────────────────────────────
async function startRabbitMQConsumer() {
  let retries = 15;
  while (retries > 0) {
    try {
      const conn = await amqp.connect(RABBITMQ_URL);
      const channel = await conn.createChannel();

      // --- Sensor + Telemetry readings (topic exchange) ---
      const telemetryExchange = 'telemetry';
      await channel.assertExchange(telemetryExchange, 'topic', { durable: true });
      const tq = await channel.assertQueue('frontend-telemetry', { exclusive: false, durable: true });
      await channel.bindQueue(tq.queue, telemetryExchange, 'sensors.normalized');
      await channel.bindQueue(tq.queue, telemetryExchange, 'telemetry.normalized'); // ← telemetry streams

      channel.consume(tq.queue, (msg) => {
        if (msg !== null) {
          try {
            const data = JSON.parse(msg.content.toString());
            // Update in-memory sensor cache with latest state
            if (data.sensor_id) sensorCache[data.sensor_id] = data;
            broadcast({ type: 'sensor_data', payload: data });
          } catch (e) {
            console.error('Failed to parse telemetry message:', e);
          }
          channel.ack(msg);
        }
      });

      // --- Alerts: triggered rules from automation-engine ---
      const alertsExchange = 'alerts';
      await channel.assertExchange(alertsExchange, 'fanout', { durable: false });
      const aq = await channel.assertQueue('', { exclusive: true });
      await channel.bindQueue(aq.queue, alertsExchange, '');

      channel.consume(aq.queue, (msg) => {
        if (msg !== null) {
          try {
            const data = JSON.parse(msg.content.toString());
            broadcast({ type: 'alert', payload: data });
          } catch (e) {
            console.error('Failed to parse alert message:', e);
          }
          channel.ack(msg);
        }
      });

      // --- Actions: triggered by automation-engine, update actuatorState ---
      const actionsExchange = 'actions';
      await channel.assertExchange(actionsExchange, 'topic', { durable: false });
      const acq = await channel.assertQueue('', { exclusive: true });
      await channel.bindQueue(acq.queue, actionsExchange, '#');

      channel.consume(acq.queue, (msg) => {
        if (msg !== null) {
          try {
            const data = JSON.parse(msg.content.toString());
            const { actuator, action, condition, ruleId } = data;
            if (actuator && action && actuatorState[actuator] !== undefined) {
              actuatorState[actuator] = {
                state: action,
                triggeredBy: `Rule #${ruleId}: ${condition}`,
                lastChange: new Date().toISOString()
              };
              console.log(`[ACT] ${actuator} → ${action} (rule #${ruleId})`);
              // Forward command to simulator
              fetch(`${SIMULATOR_URL}/api/actuators/${actuator}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ state: action })
              }).catch(err => console.error(`[ACT] Failed to forward to simulator: ${err.message}`));
              // Broadcast to frontend via WebSocket
              broadcast({ type: 'actuator_update', payload: { id: actuator, ...actuatorState[actuator] } });
            }
          } catch (e) {
            console.error('Failed to parse action message:', e);
          }
          channel.ack(msg);
        }
      });

      console.log('[AMQP] Connected. Consuming sensors, telemetry, alerts and actions.');

      conn.on('error', (err) => {
        console.error('[AMQP] Connection error:', err.message);
        setTimeout(startRabbitMQConsumer, 5000);
      });
      conn.on('close', () => {
        console.warn('[AMQP] Connection closed. Reconnecting...');
        setTimeout(startRabbitMQConsumer, 5000);
      });

      return;
    } catch (err) {
      console.error(`[AMQP] Not ready, retrying... (${retries} left): ${err.message}`);
      retries--;
      await new Promise(r => setTimeout(r, 5000));
    }
  }
  console.error('[AMQP] Could not connect after retries.');
}

// ─── Actuators API (in-memory state) ─────────────────────────────────────

const ACTUATOR_IDS = ['cooling_fan', 'entrance_humidifier', 'hall_ventilation', 'habitat_heater'];
const actuatorState = {};
ACTUATOR_IDS.forEach(id => actuatorState[id] = { state: 'OFF', triggeredBy: 'System', lastChange: null });

app.get('/actuators', (req, res) => {
  const result = ACTUATOR_IDS.map(id => ({ id, ...actuatorState[id] }));
  res.json(result);
});

app.post('/actuators/:id', async (req, res) => {
  const { id } = req.params;
  const { state } = req.body;
  if (!ACTUATOR_IDS.includes(id)) return res.status(404).json({ error: 'Unknown actuator' });
  if (state !== 'ON' && state !== 'OFF') return res.status(400).json({ error: 'State must be ON or OFF' });
  actuatorState[id] = { state, triggeredBy: 'Manual override', lastChange: new Date().toISOString() };
  console.log(`[ACT] ${id} → ${state}`);
  // Forward command to simulator
  try {
    await fetch(`${SIMULATOR_URL}/api/actuators/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state })
    });
  } catch (err) {
    console.error(`[ACT] Failed to forward to simulator: ${err.message}`);
  }
  res.json({ id, ...actuatorState[id] });
});

// ─── Rules API ────────────────────────────────────────────────────────────

app.get('/api/rules', async (req, res) => {
  try {
    const result = await db.query('SELECT * FROM rules ORDER BY id ASC');
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: 'Database error' });
  }
});

app.get('/api/rules/:id', async (req, res) => {
  try {
    const result = await db.query('SELECT * FROM rules WHERE id = $1', [req.params.id]);
    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: 'Database error' });
  }
});

app.post('/api/rules', async (req, res) => {
  const { sensor, attribute, operator, threshold, actuator, action, name } = req.body;
  if (!sensor || !attribute || !operator || threshold === undefined || !actuator || !action) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  try {
    const result = await db.query(
      'INSERT INTO rules (name, sensor, attribute, operator, threshold, actuator, action) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *',
      [name || null, sensor, attribute, operator, threshold, actuator, action]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Database error' });
  }
});

app.put('/api/rules/:id', async (req, res) => {
  const { sensor, attribute, operator, threshold, actuator, action, name } = req.body;
  if (!sensor || !attribute || !operator || threshold === undefined || !actuator || !action) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  try {
    const result = await db.query(
      'UPDATE rules SET name=$1, sensor=$2, attribute=$3, operator=$4, threshold=$5, actuator=$6, action=$7 WHERE id=$8 RETURNING *',
      [name || null, sensor, attribute, operator, threshold, actuator, action, req.params.id]
    );
    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: 'Database error' });
  }
});

app.delete('/api/rules/:id', async (req, res) => {
  try {
    const result = await db.query('DELETE FROM rules WHERE id=$1 RETURNING *', [req.params.id]);
    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Database error' });
  }
});

app.patch('/api/rules/:id/toggle', async (req, res) => {
  try {
    const result = await db.query(
      'UPDATE rules SET enabled = NOT enabled WHERE id=$1 RETURNING *',
      [req.params.id]
    );
    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: 'Database error' });
  }
});

// ─── Start ────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 8000;
server.listen(PORT, () => {
  console.log(`[SERVER] Frontend running on port ${PORT}`);
  startRabbitMQConsumer();
});