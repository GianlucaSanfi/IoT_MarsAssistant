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

// ─── WebSocket broadcast ──────────────────────────────────────────────────
const clients = new Set();

wss.on('connection', (ws) => {
  clients.add(ws);
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

      // --- Telemetry: sensor readings (topic exchange, sensors.normalized) ---
      const telemetryExchange = 'telemetry';
      await channel.assertExchange(telemetryExchange, 'topic', { durable: true });
      const tq = await channel.assertQueue('frontend-telemetry', { exclusive: false, durable: true });
      await channel.bindQueue(tq.queue, telemetryExchange, 'sensors.normalized');
      await channel.bindQueue(tq.queue, telemetryExchange, 'telemetry.normalized');

      

      channel.consume(tq.queue, (msg) => {
        if (msg !== null) {
          try {
            const data = JSON.parse(msg.content.toString());
            // data = { timestamp, sensor_id, metric, value, unit, status }
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

      console.log('[AMQP] Connected. Consuming telemetry and alerts.');

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

// ─── Rules API ────────────────────────────────────────────────────────────

app.get('/api/rules', async (req, res) => {
  try {
    const result = await db.query('SELECT * FROM rules ORDER BY id ASC');
    res.json(result.rows);
    console.log(result, "ciaooooooooooooooo!");
    ////////////////////////////////////////
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
  const { sensor, attribute, operator, threshold, actuator, action } = req.body;
  if (!sensor || !attribute || !operator || threshold === undefined || !actuator || !action) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  try {
    const result = await db.query(
      'INSERT INTO rules (sensor, attribute, operator, threshold, actuator, action) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *',
      [sensor, attribute, operator, threshold, actuator, action]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Database error' });
  }
});

app.put('/api/rules/:id', async (req, res) => {
  const { sensor, attribute, operator, threshold, actuator, action } = req.body;
  if (!sensor || !attribute || !operator || threshold === undefined || !actuator || !action) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  try {
    const result = await db.query(
      'UPDATE rules SET sensor=$1, attribute=$2, operator=$3, threshold=$4, actuator=$5, action=$6 WHERE id=$7 RETURNING *',
      [sensor, attribute, operator, threshold, actuator, action, req.params.id]
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

// ─── Start ────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 8000;
server.listen(PORT, () => {
  console.log(`[SERVER] Frontend running on port ${PORT}`);
  startRabbitMQConsumer();
});