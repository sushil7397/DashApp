import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.express as px

# Load the data
df = pd.read_csv("appointment_list.csv", low_memory=False)

address = pd.read_csv("address.csv", low_memory=False)

user = pd.read_csv("user.csv", low_memory=False)


# Parse Dates
df['appointment_date'] = pd.to_datetime(df['cdate'], errors='coerce')
user['registered_date'] = pd.to_datetime(user['cdate'], errors='coerce')

# Merge User Registration Data
df = df.merge(user[['user_id', 'registered_date']], on='user_id', how='left')

# Feature Engineering: Calculate Days to Appointment
df['days_to_appointment'] = (df['appointment_date'] - df['registered_date']).dt.days

# Filter Valid Time Gaps
df = df[df['days_to_appointment'].notnull() & (df['days_to_appointment'] >= 0)]

# Sort Appointments per User and Calculate Consecutive Differences
df = df.sort_values(by=['user_id', 'appointment_date'])
df['days_between_appointments'] = df.groupby('user_id')['appointment_date'].diff().dt.days

# Create Index for Appointment Sequence per User
df['appointment_index'] = df.groupby('user_id').cumcount() + 1

# Aggregate Average Time Between Appointments
appointment_gap_summary = (
    df
    .groupby('appointment_index')
    .agg(
        avg_days_between_appointments=('days_between_appointments', 'mean'),
        appointment_count=('appointment_id', 'count')
    )
    .reset_index()
)

# Dash App Initialization
app = dash.Dash(__name__)

# App Layout
app.layout = html.Div([
    html.H1("Registration & Consecutive Appointment Analysis", style={'textAlign': 'center'}),

    # Dropdown to filter by Registration Quarter
    html.Label("Select Registration Quarter:"),
    dcc.Dropdown(
        id='quarter-dropdown',
        options=[
            {'label': str(quarter), 'value': str(quarter)}
            for quarter in df['registered_date'].dt.to_period('Q').unique()
        ],
        value=None,
        placeholder="Select a Quarter"
    ),

    # Graph for Days to Appointment Distribution
    dcc.Graph(id='days-to-appointment-histogram'),

    # Graph for Average Days to Appointment Over Quarters
    dcc.Graph(id='avg-days-to-appointment-line'),

    # Graph for Consecutive Appointment Gaps
    dcc.Graph(id='avg-days-between-appointments-line'),

    # Display Aggregated Metrics
    html.Div(id='appointment-gap-metrics', style={'margin-top': '20px', 'textAlign': 'center'})
])

# Callback to Update Histogram Based on Quarter Selection
@app.callback(
    Output('days-to-appointment-histogram', 'figure'),
    [Input('quarter-dropdown', 'value')]
)
def update_histogram(selected_quarter):
    if selected_quarter:
        filtered_data = df[df['registered_date'].dt.to_period('Q') == selected_quarter]
    else:
        filtered_data = df
    
    fig = px.histogram(
        filtered_data,
        x='days_to_appointment',
        nbins=30,
        title="Distribution of Days Between Registration and Appointment",
        labels={'days_to_appointment': 'Days to Appointment'},
        color_discrete_sequence=['#636EFA']
    )
    fig.update_layout(
        xaxis_title='Days to Appointment',
        yaxis_title='Number of Customers',
        hovermode='x unified'
    )
    return fig

# Callback to Update Line Graph for Average Days to Appointment
@app.callback(
    Output('avg-days-to-appointment-line', 'figure'),
    [Input('quarter-dropdown', 'value')]
)
def update_avg_days_graph(selected_quarter):
    if selected_quarter:
        filtered_data = df[df['registered_date'].dt.to_period('Q') == selected_quarter]
        filtered_summary = (
            filtered_data
            .groupby('registered_date')
            .agg(avg_days_to_appointment=('days_to_appointment', 'mean'))
            .reset_index()
        )
    else:
        filtered_summary = (
            df
            .groupby('registered_date')
            .agg(avg_days_to_appointment=('days_to_appointment', 'mean'))
            .reset_index()
        )
    
    fig = px.line(
        filtered_summary,
        x='registered_date',
        y='avg_days_to_appointment',
        title="Average Days Between Registration and Appointment Over Time",
        markers=True,
        labels={'avg_days_to_appointment': 'Avg Days to Appointment', 'registered_date': 'Date'}
    )
    fig.update_layout(
        xaxis_title='Registration Date',
        yaxis_title='Average Days to Appointment',
        hovermode='x unified'
    )
    return fig

# Callback to Update Line Graph for Consecutive Appointment Differences
@app.callback(
    Output('avg-days-between-appointments-line', 'figure'),
    Input('quarter-dropdown', 'value')
)
def update_consecutive_gap_graph(selected_quarter):
    fig = px.line(
        appointment_gap_summary,
        x='appointment_index',
        y='avg_days_between_appointments',
        title='Average Days Between Consecutive Appointments',
        markers=True,
        labels={'avg_days_between_appointments': 'Avg Days Between Appointments', 'appointment_index': 'Appointment Sequence'}
    )
    fig.update_layout(
        xaxis_title='Appointment Sequence (1st-2nd, 2nd-3rd, etc.)',
        yaxis_title='Average Days Between Appointments',
        hovermode='x unified'
    )
    return fig

# Callback to Update Metrics
@app.callback(
    Output('appointment-gap-metrics', 'children'),
    [Input('quarter-dropdown', 'value')]
)
def update_metrics(selected_quarter):
    filtered_data = df if not selected_quarter else df[df['registered_date'].dt.to_period('Q') == selected_quarter]
    avg_gap = filtered_data['days_to_appointment'].mean()
    total_appointments = filtered_data['appointment_id'].nunique()
    total_customers = filtered_data['user_id'].nunique()
    
    return f"Average Days to Appointment: {avg_gap:.2f} | Total Appointments: {total_appointments} | Total Customers: {total_customers}"

# Run the app
if __name__ == '__main__':
    app.run_server(port='8052',debug=True)
