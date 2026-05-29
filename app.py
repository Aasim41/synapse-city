import streamlit as st
import json
import pandas as pd
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Smart City Traffic Optimizer",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load the data
@st.cache_data
def load_data():
    try:
        with open("dashboard_data.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

data = load_data()

if data is None:
    st.error("No training data found. Please run `train_dqn.py` first to generate `dashboard_data.json`.")
    st.stop()

# ----- HER0 -----
st.markdown("<h1 style='text-align: center;'>🚦 Smart City Traffic Optimizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #a1a1aa;'>Deep Q-Network Reinforcement Learning</p>", unsafe_allow_html=True)
st.markdown("---")

# ----- SUMMARY CARDS -----
s = data["summary"]
cols = st.columns(4)

with cols[0]:
    st.metric(
        label="Queue Improvement (vs Baseline)",
        value=f"{s['improvement_pct']:.1f}%",
        delta=f"{s['baseline_avg_queue'] - s['agent_avg_queue']:.2f} cars/step",
        delta_color="normal"
    )
with cols[1]:
    st.metric(label="Episodes Trained", value=s["episodes_trained"])
with cols[2]:
    st.metric(label="Agent Avg Queue", value=f"{s['agent_avg_queue']:.2f}")
with cols[3]:
    st.metric(label="Baseline Avg Queue", value=f"{s['baseline_avg_queue']:.2f}")

st.markdown("---")

# ----- TRAINING CHARTS -----
st.subheader("📈 Training Progress")
c1, c2 = st.columns(2)

train = data["training"]
with c1:
    st.markdown("**Episode Rewards**")
    # moving average smoothing
    s_rewards = pd.Series(train["episode_rewards"]).rolling(window=20, min_periods=1).mean()
    df_rew = pd.DataFrame({"Raw": train["episode_rewards"], "Smoothed": s_rewards})
    st.line_chart(df_rew, color=["#1e3a8a", "#3b82f6"])

with c2:
    st.markdown("**Average Queue Length**")
    s_queues = pd.Series(train["episode_avg_queues"]).rolling(window=20, min_periods=1).mean()
    df_q = pd.DataFrame({"Raw": train["episode_avg_queues"], "Smoothed": s_queues})
    st.line_chart(df_q, color=["#78350f", "#f59e0b"])

# ----- AGENT VS BASELINE & REPLAY -----
st.markdown("---")
st.subheader("🤖 Agent vs Baseline Comparison")

c3, c4 = st.columns([1, 1])

with c3:
    st.markdown("**Performance Metrics**")
    comp_df = pd.DataFrame({
        "Metric": ["Avg Queue", "Cumulative Wait"],
        "DQN Agent": [s["agent_avg_queue"], s["agent_cumulative_wait"]],
        "Fixed-Timer Baseline": [s["baseline_avg_queue"], s["baseline_cumulative_wait"]]
    }).set_index("Metric")
    
    st.bar_chart(comp_df, color=["#22c55e", "#f59e0b"])
    
    st.markdown("**Per-Lane Queue Analysis (DQN Agent)**")
    ae = data["agent_eval"]
    lane_df = pd.DataFrame({
        "North": ae["north"],
        "South": ae["south"],
        "East": ae["east"],
        "West": ae["west"]
    })
    st.line_chart(lane_df, color=["#3b82f6", "#06b6d4", "#f59e0b", "#ef4444"])

with c4:
    st.markdown("**Live Intersection Replay**")
    # Inject the data payload directly into the javascript context
    json_data = json.dumps(data)
    
    html_replay = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
      body {{ margin: 0; padding: 0; background: #0e1117; color: white; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }}
      .intersection-container {{ position: relative; width: 100%; max-width: 450px; aspect-ratio: 1/1; }}
      svg {{ width: 100%; height: 100%; }}
      .controls {{ margin-bottom: 20px; display: flex; gap: 10px; align-items: center; }}
      button {{ background: #262730; border: 1px solid #4B4B52; color: white; padding: 6px 12px; border-radius: 4px; cursor: pointer; }}
      button:hover {{ background: #333; }}
      .step-display {{ font-variant-numeric: tabular-nums; font-size: 14px; color: #a1a1aa; }}
    </style>
    </head>
    <body>
      <div class="controls">
        <button id="playBtn" onclick="togglePlay()">Pause</button>
        <button onclick="resetReplay()">Reset</button>
        <span class="step-display" id="stepDisplay">Step 0 / 300</span>
      </div>
      <div class="intersection-container" id="container"></div>

      <script>
        const DATA = {json_data};
        const cont = document.getElementById('container');
        
        // Build SVG
        function rebuildIntersectionSVG() {{
          const sz = 380, roadW = 70, halfRoad = roadW/2, cx = sz/2, cy = sz/2;
          let svg = `<svg viewBox="0 0 ${{sz}} ${{sz}}" xmlns="http://www.w3.org/2000/svg">`;
          svg += `<rect width="${{sz}}" height="${{sz}}" fill="#1A1C23" rx="12"/>`;
          svg += `<rect x="${{cx-halfRoad}}" y="0" width="${{roadW}}" height="${{sz}}" fill="#262730"/>`;
          svg += `<rect x="0" y="${{cy-halfRoad}}" width="${{sz}}" height="${{roadW}}" fill="#262730"/>`;
          svg += `<rect x="${{cx-halfRoad}}" y="${{cy-halfRoad}}" width="${{roadW}}" height="${{roadW}}" fill="#262730"/>`;
          
          const dash = `stroke="#4B4B52" stroke-width="1.5" stroke-dasharray="8 6"`;
          svg += `<line x1="${{cx}}" y1="0" x2="${{cx}}" y2="${{cy-halfRoad}}" ${{dash}}/>`;
          svg += `<line x1="${{cx}}" y1="${{cy+halfRoad}}" x2="${{cx}}" y2="${{sz}}" ${{dash}}/>`;
          svg += `<line x1="0" y1="${{cy}}" x2="${{cx-halfRoad}}" y2="${{cy}}" ${{dash}}/>`;
          svg += `<line x1="${{cx+halfRoad}}" y1="${{cy}}" x2="${{sz}}" y2="${{cy}}" ${{dash}}/>`;

          svg += `<circle id="light-ns" cx="${{cx-18}}" cy="${{cy-halfRoad-12}}" r="6" fill="#ef4444"/>`;
          svg += `<circle id="light-ns2" cx="${{cx+18}}" cy="${{cy+halfRoad+12}}" r="6" fill="#ef4444"/>`;
          svg += `<circle id="light-ew" cx="${{cx+halfRoad+12}}" cy="${{cy-18}}" r="6" fill="#ef4444"/>`;
          svg += `<circle id="light-ew2" cx="${{cx-halfRoad-12}}" cy="${{cy+18}}" r="6" fill="#ef4444"/>`;

          svg += `<g id="cars-north"></g><g id="cars-south"></g><g id="cars-east"></g><g id="cars-west"></g>`;
          svg += `</svg>`;
          cont.innerHTML = svg;
        }}

        function updateIntersectionStep(step) {{
          const ae = DATA.agent_eval;
          if(step >= ae.north.length) return;
          const action = ae.actions[step]; 
          const nsGreen = action === 0;
          const gc = '#22c55e', rc = '#ef4444';

          const sf = (id,c) => document.getElementById(id).setAttribute('fill', c);
          sf('light-ns', nsGreen ? gc : rc);
          sf('light-ns2', nsGreen ? gc : rc);
          sf('light-ew', nsGreen ? rc : gc);
          sf('light-ew2', nsGreen ? rc : gc);

          const cx=190, cy=190, hr=35, cw=10, ch=6, cg=2;

          function drawCars(groupId, count, dir) {{
            const g = document.getElementById(groupId);
            const maxCars = Math.min(count, 14);
            let html = '';
            for(let i=0; i<maxCars; i++) {{
              let x,y,w,h;
              const col = count>8 ? '#ef4444' : count>4 ? '#f59e0b' : '#3b82f6';
              if(dir==='north') {{ w=ch; h=cw; x=cx-hr+8; y=cy-hr-16-(cw+cg)*i; }}
              else if(dir==='south') {{ w=ch; h=cw; x=cx+hr-8-ch; y=cy+hr+6+(cw+cg)*i; }}
              else if(dir==='east') {{ w=cw; h=ch; x=cx+hr+6+(cw+cg)*i; y=cy-hr+8; }}
              else {{ w=cw; h=ch; x=cx-hr-6-(cw+cg)*i-cw; y=cy+hr-8-ch; }}
              html += `<rect x="${{x}}" y="${{y}}" width="${{w}}" height="${{h}}" rx="2" fill="${{col}}" opacity=".9"/>`;
            }}
            if(count>0) {{
              let bx,by;
              if(dir==='north') {{ bx=cx-hr+20; by=cy-hr-18-(cw+cg)*Math.min(maxCars,3)-2; }}
              else if(dir==='south') {{ bx=cx+hr-20; by=cy+hr+14+(cw+cg)*Math.min(maxCars,3)+12; }}
              else if(dir==='east') {{ bx=cx+hr+14+(cw+cg)*Math.min(maxCars,3)+12; by=cy-hr+14; }}
              else {{ bx=cx-hr-14-(cw+cg)*Math.min(maxCars,3)-18; by=cy+hr-14; }}
              html += `<text x="${{bx}}" y="${{by}}" font-size="10" fill="#a1a1aa" text-anchor="middle">${{count}}</text>`;
            }}
            g.innerHTML = html;
          }}

          drawCars('cars-north', ae.north[step], 'north');
          drawCars('cars-south', ae.south[step], 'south');
          drawCars('cars-east', ae.east[step], 'east');
          drawCars('cars-west', ae.west[step], 'west');

          document.getElementById('stepDisplay').innerText = `Step ${{step+1}} / ${{ae.north.length}}`;
        }}

        let step=0, playing=true, iv=null;
        
        function start() {{
          if(iv) clearInterval(iv);
          iv = setInterval(() => {{
            if(!playing) return;
            updateIntersectionStep(step);
            step++;
            if(step >= DATA.agent_eval.north.length) step = 0;
          }}, 180);
        }}

        function togglePlay() {{
          playing = !playing;
          document.getElementById('playBtn').innerText = playing ? 'Pause' : 'Play';
        }}

        function resetReplay() {{
          step = 0;
          updateIntersectionStep(0);
        }}

        rebuildIntersectionSVG();
        start();
      </script>
    </body>
    </html>
    """
    
    components.html(html_replay, height=550)

# ----- EXPLORATION DECAY -----
st.markdown("---")
st.subheader("🔍 Exploration Rate Decay")
st.line_chart(train["episode_epsilons"], color="#a855f7")

st.markdown("<p style='text-align: center; color: #a1a1aa; font-size: 14px;'>Built with NumPy, Gymnasium & Streamlit</p>", unsafe_allow_html=True)
