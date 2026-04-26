from machine import Pin, PWM
import network
import socket
import time


led = Pin("LED", Pin.OUT)
pwm = PWM(Pin(16))
pwm.freq(1000)
pwm_value = 0
wlan = network.WLAN(network.STA_IF)


def set_pwm(value):
    global pwm_value
    pwm_value = max(0, min(100, int(value)))
    pwm.duty_u16(pwm_value * 65535 // 100)
    return pwm_value


set_pwm(pwm_value)


def wait_for_wifi(timeout_s=30):
    start = time.time()
    while not wlan.isconnected():
        if time.time() - start >= timeout_s:
            raise RuntimeError("Wi-Fi connection timed out")
        time.sleep(0.25)
    return wlan.ifconfig()[0]


def page(ip):
    led_state = "ON" if led.value() else "OFF"
    button_label = "Turn off" if led.value() else "Turn on"
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pico LED</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      min-height: 100svh;
      display: grid;
      place-items: center;
      background: #f4f7f8;
      color: #111;
    }
    main {
      width: min(92vw, 360px);
      text-align: center;
    }
    h1 {
      margin: 0 0 12px;
      font-size: 32px;
    }
    p {
      margin: 8px 0 22px;
      font-size: 18px;
    }
    button {
      display: inline-block;
      padding: 16px 26px;
      border: 0;
      border-radius: 8px;
      background: #157a6e;
      color: white;
      font-size: 20px;
      font-weight: 700;
      cursor: pointer;
    }
    button:disabled {
      cursor: wait;
      opacity: 0.75;
    }
    .dial-wrap {
      display: grid;
      place-items: center;
      margin: 30px auto 12px;
    }
    .dial {
      --angle: 0deg;
      width: 220px;
      height: 220px;
      border: 0;
      border-radius: 50%;
      position: relative;
      display: grid;
      place-items: center;
      background:
        conic-gradient(#157a6e var(--angle), #d2d9dc 0),
        #d2d9dc;
      color: #111;
      cursor: grab;
      touch-action: none;
    }
    .dial:active {
      cursor: grabbing;
    }
    .dial::before {
      content: "";
      position: absolute;
      inset: 18px;
      border-radius: 50%;
      background: #f4f7f8;
      box-shadow: inset 0 0 0 1px #c5ced2;
    }
    .dial::after {
      content: "";
      position: absolute;
      left: 50%;
      top: 50%;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #111;
      margin: -8px 0 0 -8px;
      transform: rotate(var(--angle)) translateY(-93px);
      transform-origin: center;
    }
    .dial-value {
      position: relative;
      z-index: 1;
      display: grid;
      gap: 2px;
    }
    .dial-number {
      font-size: 52px;
      font-weight: 700;
      line-height: 1;
    }
    .dial-label {
      font-size: 14px;
      letter-spacing: 0;
    }
    .pwm-off {
      margin-top: 10px;
      background: #353a3d;
    }
  </style>
</head>
<body>
  <main>
    <h1>Pico LED</h1>
    <p>LED is <strong id="state">""" + led_state + """</strong></p>
    <button id="toggle" type="button">""" + button_label + """</button>
    <div class="dial-wrap">
      <button
        class="dial"
        id="dial"
        type="button"
        aria-label="PWM value on GPIO16"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=\"""" + str(pwm_value) + """\"
      >
        <span class="dial-value">
          <span class="dial-number" id="pwmValue">""" + str(pwm_value) + """</span>
          <span class="dial-label">GPIO16 PWM</span>
        </span>
      </button>
    </div>
    <button class="pwm-off" id="pwmOff" type="button">Fade PWM off</button>
    <p>""" + ip + """</p>
  </main>
  <script>
    const state = document.getElementById("state");
    const toggle = document.getElementById("toggle");
    const dial = document.getElementById("dial");
    const pwmValue = document.getElementById("pwmValue");
    const pwmOff = document.getElementById("pwmOff");
    let pwm = """ + str(pwm_value) + """;
    let dragging = false;
    let sendTimer = 0;
    let fadeFrame = 0;
    let lastFadeSend = 0;

    function render(data) {
      state.textContent = data.on ? "ON" : "OFF";
      toggle.textContent = data.on ? "Turn off" : "Turn on";
    }

    function renderPwm(value) {
      pwm = Math.max(0, Math.min(100, Math.round(value)));
      pwmValue.textContent = pwm;
      dial.setAttribute("aria-valuenow", pwm);
      dial.style.setProperty("--angle", `${pwm * 3.6}deg`);
    }

    async function sendPwm() {
      await fetch(`/pwm?value=${pwm}`, { cache: "no-store" });
    }

    function queuePwmSend() {
      clearTimeout(sendTimer);
      sendTimer = setTimeout(sendPwm, 80);
    }

    function updateFromPointer(event) {
      cancelFade();
      const rect = dial.getBoundingClientRect();
      const x = event.clientX - (rect.left + rect.width / 2);
      const y = event.clientY - (rect.top + rect.height / 2);
      const degrees = (Math.atan2(y, x) * 180 / Math.PI + 450) % 360;
      renderPwm(degrees / 3.6);
      queuePwmSend();
    }

    function cancelFade() {
      if (fadeFrame) {
        cancelAnimationFrame(fadeFrame);
        fadeFrame = 0;
      }
      pwmOff.disabled = false;
    }

    function fadePwmOff() {
      cancelFade();
      const startValue = pwm;
      const startTime = performance.now();
      const duration = 3000;
      pwmOff.disabled = true;

      function step(now) {
        const elapsed = Math.min(duration, now - startTime);
        const nextValue = startValue * (1 - elapsed / duration);
        renderPwm(nextValue);

        if (now - lastFadeSend > 90 || elapsed === duration) {
          lastFadeSend = now;
          sendPwm();
        }

        if (elapsed < duration) {
          fadeFrame = requestAnimationFrame(step);
        } else {
          renderPwm(0);
          sendPwm();
          fadeFrame = 0;
          pwmOff.disabled = false;
        }
      }

      fadeFrame = requestAnimationFrame(step);
    }

    toggle.addEventListener("click", async () => {
      toggle.disabled = true;
      try {
        const response = await fetch("/toggle", { cache: "no-store" });
        render(await response.json());
      } finally {
        toggle.disabled = false;
      }
    });

    dial.addEventListener("pointerdown", (event) => {
      dragging = true;
      dial.setPointerCapture(event.pointerId);
      updateFromPointer(event);
    });

    dial.addEventListener("pointermove", (event) => {
      if (dragging) {
        updateFromPointer(event);
      }
    });

    dial.addEventListener("pointerup", async () => {
      dragging = false;
      clearTimeout(sendTimer);
      await sendPwm();
    });

    dial.addEventListener("keydown", async (event) => {
      if (event.key === "ArrowRight" || event.key === "ArrowUp") {
        event.preventDefault();
        cancelFade();
        renderPwm(pwm + 1);
        await sendPwm();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
        event.preventDefault();
        cancelFade();
        renderPwm(pwm - 1);
        await sendPwm();
      }
    });

    pwmOff.addEventListener("click", fadePwmOff);

    renderPwm(pwm);
  </script>
</body>
</html>"""


def led_json():
    return '{{"on":{}}}'.format("true" if led.value() else "false")


def pwm_json():
    return '{{"value":{},"pin":16}}'.format(pwm_value)


def send_response(conn, body, status="200 OK", content_type="text/html"):
    conn.send("HTTP/1.1 {}\r\n".format(status))
    conn.send("Content-Type: {}\r\n".format(content_type))
    conn.send("Content-Length: {}\r\n".format(len(body)))
    conn.send("Connection: close\r\n\r\n")
    conn.sendall(body)


def serve():
    ip = wait_for_wifi()
    print("Web server listening at http://{}/".format(ip))

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(addr)
    server.listen(1)

    while True:
        conn, addr = server.accept()
        try:
            request = conn.recv(1024).decode()
            request_line = request.split("\r\n", 1)[0]
            path = request_line.split(" ")[1] if request_line else "/"

            if path == "/toggle":
                led.value(0 if led.value() else 1)
                send_response(conn, led_json(), content_type="application/json")
                continue
            elif path.startswith("/pwm?value="):
                value = path.split("=", 1)[1].split("&", 1)[0]
                set_pwm(value)
                send_response(conn, pwm_json(), content_type="application/json")
                continue
            elif path == "/" or path == "/index.html":
                body = page(ip)
            elif path == "/favicon.ico":
                send_response(conn, "", "204 No Content", "text/plain")
                continue
            else:
                body = "Not found"
                send_response(conn, body, "404 Not Found", "text/plain")
                continue

            send_response(conn, body)
        except Exception as exc:
            print("Request failed:", exc)
        finally:
            conn.close()


serve()
