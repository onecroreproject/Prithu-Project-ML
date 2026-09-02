module.exports = {
  apps: [
    {
      name: "prithu-ml-engine",
      script: "venv/bin/uvicorn", // On Linux, the venv path is bin/ not Scripts/
      args: "main:app --host 0.0.0.0 --port 8001 --workers 2",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
      }
    }
  ]
};
