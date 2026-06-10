const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');

const PID_FILE = path.resolve(__dirname, '.server-pid');
const TEST_DB = path.resolve(__dirname, 'test_db.sqlite3');

module.exports = async function () {
  try {
    if (fs.existsSync(PID_FILE)) {
      const pid = parseInt(fs.readFileSync(PID_FILE, 'utf-8').trim(), 10);
      try {
        process.kill(pid, 'SIGTERM');
      } catch {
        try {
          execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' });
        } catch {}
      }
      try { fs.unlinkSync(PID_FILE); } catch {}
      console.log(`\n=== Killed server process ${pid} ===`);
    }
    if (fs.existsSync(TEST_DB)) {
      try { fs.unlinkSync(TEST_DB); } catch {}
      console.log('=== Removed test database ===');
    }
  } catch (err) {
    console.error('Teardown error:', err.message);
  }
};
