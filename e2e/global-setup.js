const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PROJECT_DIR = path.resolve(__dirname, '..');
const PID_FILE = path.resolve(__dirname, '.server-pid');

const PYTHON = findPython();

function findPython() {
  const candidates = [
    path.resolve(PROJECT_DIR, '.venv', 'Scripts', 'python.exe'),
    path.resolve(PROJECT_DIR, '.venv', 'bin', 'python'),
    'python',
    'python3',
  ];
  for (const c of candidates) {
    try {
      execSync(`"${c}" --version`, { stdio: 'ignore' });
      return c;
    } catch {}
  }
  return 'python';
}

function migrateAndSeed() {
  const env = { ...process.env, DJANGO_SETTINGS_MODULE: 'config.settings.test' };
  const testDb = path.resolve(__dirname, 'test_db.sqlite3');
  try { fs.unlinkSync(testDb); } catch {}
  execSync(`"${PYTHON}" manage.py migrate`, { cwd: PROJECT_DIR, env, stdio: 'inherit' });
  execSync(`"${PYTHON}" manage.py seed_e2e`, { cwd: PROJECT_DIR, env, stdio: 'inherit' });
}

function startServer() {
  return new Promise((resolve, reject) => {
    const env = { ...process.env, DJANGO_SETTINGS_MODULE: 'config.settings.test', PYTHONUNBUFFERED: '1' };

    const proc = spawn(PYTHON, ['manage.py', 'runserver', '--noreload', '--nothreading'], {
      cwd: PROJECT_DIR,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: true,
    });

    let started = false;

    const onOutput = (data) => {
      const text = data.toString();
      if (!started && text.includes('Starting development server')) {
        started = true;
        fs.writeFileSync(PID_FILE, String(proc.pid));
        resolve();
      }
    };

    proc.stdout.on('data', onOutput);
    proc.stderr.on('data', onOutput);

    proc.on('error', (err) => { if (!started) reject(err); });
    proc.on('exit', (code) => { if (!started) reject(new Error(`Server exited with code ${code}`)); });

    setTimeout(() => { if (!started) { proc.kill(); reject(new Error('Server start timed out')); } }, 30000);
  });
}

module.exports = async function () {
  console.log(`=== Using Python: ${PYTHON} ===`);
  console.log('=== Setting up E2E test data ===');
  migrateAndSeed();
  console.log('=== Starting Django server ===');
  await startServer();
  console.log('=== Django server ready on http://localhost:8000 ===');
};
