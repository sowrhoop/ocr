const path = require('path');
const express = require('express');
const app = express();

const PORT = parseInt(process.env.PORT || '9090', 10);

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/status', (_req, res) => {
  res.json({ service: 'b', status: 'ok' });
});

app.get('/', (_req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Project 2 listening on ${PORT}`);
});

