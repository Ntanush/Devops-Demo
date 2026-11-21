import os
import time
import socket
from flask import Flask, jsonify, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

VERSION = os.getenv("APP_VERSION", "v1")
COLOR = os.getenv("APP_COLOR", "#2b7de9")

REQUESTS = Counter("app_requests_total", "Total requests", ["endpoint", "version"])
LATENCY = Histogram("app_request_seconds", "Request latency", ["endpoint"])


@app.route("/")
def home():
    REQUESTS.labels("/", VERSION).inc()
    with LATENCY.labels("/").time():
        return f"""
        <html><body style="font-family:sans-serif;background:{COLOR};color:white;text-align:center;padding-top:15%">
          <h1>DevOps Demo</h1>
          <h2>Version: {VERSION}</h2>
          <p>Served by pod: {socket.gethostname()}</p>
        </body></html>
        """


@app.route("/health")
def health():
    return jsonify(status="UP", version=VERSION)


@app.route("/load")
def load():
    """Burns CPU for ~0.2s so you can watch the HPA scale out."""
    REQUESTS.labels("/load", VERSION).inc()
    end = time.time() + 0.2
    x = 0
    while time.time() < end:
        x += 1
    return jsonify(work=x, pod=socket.gethostname())


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
