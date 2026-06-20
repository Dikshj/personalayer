fetch("http://127.0.0.1:7823/daemon/status")
  .then(() => document.getElementById("status").textContent = "Connected")
  .catch(() => document.getElementById("status").textContent = "Local runtime not running");
