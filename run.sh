#!/bin/bash
cd /Users/grantharrison/Documents/Claude/Cognita/data-dashboards/attribution-dashboard
pkill -f "streamlit run" 2>/dev/null
sleep 1
mkdir -p ~/.streamlit
cat > ~/.streamlit/credentials.toml << 'EOF'
[general]
email = ""
EOF
.venv/bin/streamlit run app.py --server.headless true --server.runOnSave true
