// AutoFix Standard Logging — Node.js (pino)
// ============================================
// Install:
//   npm install pino pino-multi-stream --save
//
// Save this file as: src/logger.js  (or src/logger.ts for TypeScript)
// Import it everywhere logging is needed:
//   const logger = require('./logger');           // CommonJS
//   import logger from './logger';                // ES Modules / TypeScript
//
// pino natively outputs newline-delimited JSON (NDJSON) which is perfect for
// AutoFix log monitoring.
// AutoFix watches for lines where "level" >= 50 (error in pino's numeric scale:
//   10=trace, 20=debug, 30=info, 40=warn, 50=error, 60=fatal).

'use strict';

const fs   = require('fs');
const path = require('path');
const pino = require('pino');

// ---------------------------------------------------------------------------
// Configuration — adjust via environment variables
// ---------------------------------------------------------------------------
const LOG_PATH  = process.env.LOG_FILE  || path.join('logs', 'app.log');
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';
const SERVICE   = process.env.SERVICE_NAME || path.basename(process.cwd());

// Ensure logs directory exists before opening the file stream
fs.mkdirSync(path.dirname(LOG_PATH), { recursive: true });

// ---------------------------------------------------------------------------
// Multi-destination: stdout + rotating log file
// pino writes to one stream; for multiple streams use pino-multi-stream
// ---------------------------------------------------------------------------
const streams = [
  // Stdout — required for Docker `docker logs -f` compatibility
  { stream: process.stdout },

  // File stream (append; use logrotate or a cron job for rotation)
  { stream: fs.createWriteStream(LOG_PATH, { flags: 'a' }) },
];

// ---------------------------------------------------------------------------
// Logger instance
// ---------------------------------------------------------------------------
let logger;

try {
  const pinoMultiStream = require('pino-multi-stream');
  logger = pinoMultiStream.multistream
    ? pino({ level: LOG_LEVEL, base: { service: SERVICE, pid: process.pid } },
           pinoMultiStream.multistream(streams))
    : pino({ level: LOG_LEVEL, base: { service: SERVICE, pid: process.pid } },
           pino.multistream(streams));
} catch (_) {
  // Fallback: stdout only if pino-multi-stream is not installed
  logger = pino(
    { level: LOG_LEVEL, base: { service: SERVICE, pid: process.pid } },
    process.stdout
  );
}

// ---------------------------------------------------------------------------
// Example usage (delete before committing to the application)
// ---------------------------------------------------------------------------
//
// const logger = require('./logger');
//
// // Informational event
// logger.info({ port: 8080, env: process.env.NODE_ENV }, 'Server started');
//
// // Warning with context object (pino style: object first, message second)
// logger.warn({ latencyMs: 850, host: DB_HOST }, 'Database connection slow');
//
// // Error with Error object — pino serializes err.message + err.stack
// try {
//   connectToDatabase();
// } catch (err) {
//   logger.error({ err, host: DB_HOST }, 'Database connection failed');
// }
//
// // Fatal — pino uses numeric level 60
// process.on('uncaughtException', (err) => {
//   logger.fatal({ err }, 'Uncaught exception');
//   process.exit(1);
// });

module.exports = logger;
