// AutoFix Standard Logging — Node.js (winston)
// ==============================================
// Install:
//   npm install winston winston-daily-rotate-file --save
//
// Save this file as: src/logger.js  (or src/logger.ts for TypeScript)
// Import it everywhere logging is needed:
//   const logger = require('./logger');           // CommonJS
//   import logger from './logger';                // ES Modules / TypeScript
//
// The produced JSON matches the AutoFix canonical schema:
//   {"timestamp":"...","level":"error","message":"...","service":"app",...}
// AutoFix watches for lines where "level" is "error", "warn", or "crit".

'use strict';

const path = require('path');
const winston = require('winston');

// ---------------------------------------------------------------------------
// Configuration — adjust LOG_PATH and LOG_LEVEL via environment variables
// ---------------------------------------------------------------------------
const LOG_PATH  = process.env.LOG_FILE  || path.join('logs', 'app.log');
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';
const SERVICE   = process.env.SERVICE_NAME || path.basename(process.cwd());

// Ensure logs directory exists
const fs = require('fs');
fs.mkdirSync(path.dirname(LOG_PATH), { recursive: true });

// ---------------------------------------------------------------------------
// Custom log format — produces AutoFix-compatible JSON lines
// ---------------------------------------------------------------------------
const jsonFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DDTHH:mm:ss.SSSZ' }),
  winston.format.errors({ stack: true }),          // include stack traces
  winston.format.splat(),                          // support printf-style %s/%d
  winston.format.json()                            // final JSON serialization
);

// ---------------------------------------------------------------------------
// Logger instance
// ---------------------------------------------------------------------------
const logger = winston.createLogger({
  level: LOG_LEVEL,
  format: jsonFormat,
  defaultMeta: {
    service: SERVICE,
    pid: process.pid,
  },
  transports: [
    // Stdout — required for Docker `docker logs -f` compatibility
    new winston.transports.Console({
      handleExceptions: true,
      handleRejections: true,
    }),

    // Rotating file — 50 MB per file, keep 7 days / 7 files
    new winston.transports.File({
      filename: LOG_PATH,
      maxsize: 50 * 1024 * 1024,    // 50 MB
      maxFiles: 7,
      tailable: true,
      handleExceptions: true,
      handleRejections: true,
    }),
  ],
  exitOnError: false,
});

// ---------------------------------------------------------------------------
// Example usage (delete before committing to the application)
// ---------------------------------------------------------------------------
//
// const logger = require('./logger');
//
// // Informational event
// logger.info('Server started', { port: 8080, env: process.env.NODE_ENV });
//
// // Warning with context
// logger.warn('Database connection slow', { latencyMs: 850, host: DB_HOST });
//
// // Error with exception
// try {
//   connectToDatabase();
// } catch (err) {
//   logger.error('Database connection failed', {
//     message: err.message,
//     stack:   err.stack,
//     host:    DB_HOST,
//   });
// }
//
// // Critical / fatal
// process.on('uncaughtException', (err) => {
//   logger.error('Uncaught exception', { message: err.message, stack: err.stack });
//   process.exit(1);
// });

module.exports = logger;
