import os
from dash import Dash, html, dcc, Input, Output
import dash_table
import plotly.express as px
import pandas as pd

# Import your existing modules
from position_tracker import get_successful_copied_trades, get_market_info, get_current_market_prices

# Initialize Dash app
app = Dash(__name__)
server = app.server  # for WSGI

# Helper: fetch and transform data
def fetch_positions_df():
    # Load copied trades
    trades = get_successful_copied_trades()
    rows = []
    for t in trades:
        cond_id = t["condition_id"]
        token_id = t["token_id"]
        size = t["size"]
        avg_price = t["avg_price"]

        # Get current price
        current = get_current_market_prices(cond_id, token_id)

        # Compute PnL
        pnl = (current - avg_price) * size

        # Market metadata
        market = get_market_info(cond_id)
        question = market.get("question_text")
        rows.append({
            "Market": question,
            "Token ID": token_id,
            "Size": size,
            "Avg Price": avg_price,
            "Current Price": current,
            "PnL": pnl,
        })
    return pd.DataFrame(rows)

# Layout
app.layout = html.Div([
    html.H1("Polymarket CopyTrader Dashboard", style={"textAlign": "center"}),
    dcc.Interval(id="interval", interval=10*1000, n_intervals=0),  # refresh every 10s
    html.Div(id="summary-cards", style={"display": "flex", "justifyContent": "space-around", "margin": "20px"}),

    dash_table.DataTable(
        id='positions-table',
        columns=[{"name": i, "id": i} for i in ["Market", "Token ID", "Size", "Avg Price", "Current Price", "PnL"]],
        data=[],
        style_cell={"textAlign": "left", "padding": "5px"},
        style_header={"fontWeight": "bold"},
        sort_action="native",
        filter_action="native",
        page_size=10,
    ),

    dcc.Graph(id='pnl-chart')
])

# Callbacks
@app.callback(
    [Output('positions-table', 'data'),
     Output('pnl-chart', 'figure'),
     Output('summary-cards', 'children')],
    Input('interval', 'n_intervals')
)
def update_dashboard(n):
    df = fetch_positions_df()

    # Summary cards
    total_pnl = df['PnL'].sum()
    invested = (df['Avg Price'] * df['Size']).sum()
    roi = total_pnl / invested * 100 if invested else 0

    cards = [
        html.Div([html.H3("Total PnL"), html.P(f"${total_pnl:.2f}")], style={"border": "1px solid #ccc", "padding": "10px", "borderRadius": "8px"}),
        html.Div([html.H3("Invested"), html.P(f"${invested:.2f}")], style={"border": "1px solid #ccc", "padding": "10px", "borderRadius": "8px"}),
        html.Div([html.H3("ROI %"), html.P(f"{roi:.2f}%")], style={"border": "1px solid #ccc", "padding": "10px", "borderRadius": "8px"}),
    ]

    # PnL bar chart
    fig = px.bar(df, x='Market', y='PnL', title='PnL by Market')

    return df.to_dict('records'), fig, cards

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=True, host='0.0.0.0', port=port)
