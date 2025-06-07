import streamlit as st
import pandas as pd
import numpy as np                 #  ← NOVO
import paho.mqtt.client as mqtt
import json, time, queue, logging, random, joblib, os, smtplib
from email.mime.text import MIMEText
from collections import deque

# ───── Configurações MQTT ────────────────────────────────────
BROKER = "broker.hivemq.com"
PORT   = 1883
TOPIC  = "fiap/gs2025/flood"

# ───── Configurações de e-mail via SendGrid (SMTP) ───────────
SMTP_SERVER = "smtp.sendgrid.net"
SMTP_PORT   = 587
EMAIL_FROM  = "pedroscofield2@hotmail.com"        # remetente verificado
EMAIL_USER  = "apikey"
EMAIL_PASS  = os.getenv("SENDGRID_KEY")           # API-key
EMAIL_TO    = "	pedroscofield513@gmail.com"         # destinatário

print(f"SENDGRID_KEY set = {bool(EMAIL_PASS)}")

def send_email(subject: str, body: str):
    if not EMAIL_PASS:
        print("SENDGRID_KEY ausente — alerta suprimido."); return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_FROM, EMAIL_TO
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls(); s.login(EMAIL_USER, EMAIL_PASS); s.send_message(msg)
            print("E-mail enviado para", EMAIL_TO)
    except Exception as e:
        print("Falha ao enviar e-mail:", e)

# ───── Modelo de Machine Learning ────────────────────────────
model = joblib.load("risk_model.pkl")
rain_buf = deque(maxlen=5)

FORCE_RISK = True          # ← coloque False após o teste

# ───── Interface Streamlit ───────────────────────────────────
st.set_page_config(page_title="Flood Monitor", layout="centered")
st.title("🌊  Flood Monitor – GS 2025")

if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(
        columns=["ts","nivel","perc","temp","ur","alarm","risco"]
    )
if "mail_sent" not in st.session_state:
    st.session_state.mail_sent = False

metrics_ph, chart_ph = st.empty(), st.empty()
msg_queue: queue.Queue = queue.Queue(maxsize=100)

def draw_dashboard():
    df = st.session_state.df
    if df.empty:
        metrics_ph.info("Aguardando dados MQTT…"); chart_ph.empty(); return
    lat = df.iloc[-1]
    with metrics_ph.container():
        c1,c2,c3 = st.columns(3)
        c1.metric("Nível (cm)", f"{lat.nivel:.0f}")
        c2.metric("Enchimento %", f"{lat.perc:.0f}%")
        c3.metric("Temp (°C)", f"{lat.temp:.1f}")
        if lat.alarm: st.error("🚨 **ALERTA** – nível acima do limiar!")
        if lat.risco == 1: st.warning("⚠️ **ML alerta:** risco de enchente!")
    df_plot = (df.set_index("ts")[["nivel","perc"]]
                 .apply(pd.to_numeric, errors="coerce")
                 .interpolate(limit_direction="both"))
    chart_ph.line_chart(df_plot, height=300)

# ───── Callbacks MQTT ─────────────────────────────────────────
def on_connect(c,u,f,rc): print("MQTT conectado – rc =", rc); c.subscribe(TOPIC)
def on_message(c,u,m):
    if m.payload.startswith(b'{'):
        try: msg_queue.put_nowait(m.payload)
        except queue.Full: pass

logging.basicConfig(level=logging.INFO)
client = mqtt.Client(protocol=mqtt.MQTTv311)
client.on_connect, client.on_message = on_connect, on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

# ───── Loop principal ────────────────────────────────────────
draw_dashboard()

while True:
    try:
        payload = msg_queue.get(timeout=1)
        data = json.loads(payload)

        # ------ Dados recebidos ------------------------------
        new_row = {
            "ts":    pd.Timestamp.now(),
            "nivel": data.get("w"),
            "perc":  data.get("p"),
            "temp":  data.get("t"),
            "ur":    data.get("h"),
            "alarm": data.get("alarm"),
        }

        # ------ Chuva ----------------------------------------
        chuva_dia = data.get("rain") or random.uniform(0, 50)
        rain_buf.append(chuva_dia)
        chuva_3d = sum(list(rain_buf)[-3:])
        chuva_5d = sum(rain_buf)

        # ------ Predição ML (agora com nomes) ----------------
        X = pd.DataFrame(np.array([[chuva_dia, chuva_3d, chuva_5d]]),
                         columns=["chuva_dia","chuva_3d","chuva_5d"])
        risco = int(model.predict(X)[0])
        if FORCE_RISK: risco = 1
        new_row["risco"] = risco

        # ------ Atualiza histórico ---------------------------
        st.session_state.df = (
            pd.concat([st.session_state.df, pd.DataFrame([new_row])])
              .tail(500)
        )

        # ------ E-mail de alerta -----------------------------
        if risco == 1 and not st.session_state.mail_sent:
            subj = "🚨 Alerta de enchente – modelo ML"
            body = (f"Risco elevado detectado!\n\n"
                    f"Nível: {new_row['nivel']:.0f} cm ({new_row['perc']:.0f} %)\n"
                    f"Temp/UR: {new_row['temp']:.1f} °C / {new_row['ur']:.0f} %\n"
                    f"Data/hora: {new_row['ts']}\n")
            send_email(subj, body)
            st.session_state.mail_sent = True
        elif risco == 0:
            st.session_state.mail_sent = False

        draw_dashboard()

    except queue.Empty:
        pass

    time.sleep(0.1)
