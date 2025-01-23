import pandas as pd
import dash
from dash import dcc, html, Input, Output, State
import plotly.express as px
import datetime

# ----------------- Load Data -----------------

# Load appointment data
appointment = pd.read_csv(
    r'appointment_list.csv',
    low_memory=False
)

# Ensure appointment_date is in datetime format
appointment['appointment_date'] = pd.to_datetime(appointment['cdate'])

# Convert user_id and g_id to string
appointment['user_id'] = appointment['user_id'].astype(str)
appointment['g_id'] = appointment['g_id'].astype(str)

# Fill missing values
appointment.fillna(0, inplace=True)

# Load user data
user = pd.read_csv(
    r'user.csv',
    low_memory=False
)
user['user_id'] = user['user_id'].astype(str)

# Ensure expected columns exist
if 'email' not in user.columns:
    user['email'] = 'No Email'

user = user[['user_id', 'email']]

# Load address data
address = pd.read_csv(
    r'address.csv',
    low_memory=False
)
address['user_id'] = address['user_id'].astype(str)
address = address[['user_id', 'state']]

# Merge data
appointment = pd.merge(appointment, address, on='user_id', how='left')
appointment = pd.merge(appointment, user, on='user_id', how='left')

# Fill missing states and user emails with placeholders
appointment['state'] = appointment['state'].fillna('Unknown')
appointment['email'] = appointment['email'].fillna('No Email')

# ----------------- User Classification Logic -----------------

today = datetime.datetime.now()

# Get last appointment date per user
user_last_appointment = appointment.groupby('user_id')['appointment_date'].max().reset_index()
user_last_appointment['days_since_last_appointment'] = (today - user_last_appointment['appointment_date']).dt.days

# Add user classification
def classify_user(days):
    if pd.isna(days):
        return 'No Appointments'
    elif days < 90:
        return 'Potential'
    elif days < 180:
        return 'Inactive (6 Months)'
    elif days > 360:
        return 'Lost'
    else:
        return 'Recurring'

user_last_appointment['user_status'] = user_last_appointment['days_since_last_appointment'].apply(classify_user)

# Merge classification back to user data
user_data = pd.merge(user_last_appointment, user, on='user_id', how='left')

# ----------------- Dash App Setup -----------------
app = dash.Dash(__name__)

# Get unique states for dropdown
unique_states = appointment['state'].unique()
state_options = [{'label': state, 'value': state} for state in unique_states]

# Get user status options
status_options = [
    {'label': 'All', 'value': 'All'},
    {'label': 'Potential', 'value': 'Potential'},
    {'label': 'Inactive (6 Months)', 'value': 'Inactive (6 Months)'},
    {'label': 'Lost', 'value': 'Lost'},
    {'label': 'Recurring', 'value': 'Recurring'}
]


app.layout = html.Div([
    html.H1("Appointment Analytics: User and Status Segmentation", style={'textAlign': 'center'}),

    html.Label("Filter by State:"),
    dcc.Dropdown(
        id='state-dropdown',
        options=state_options,
        value=None,
        placeholder="Select a state"
    ),

    html.Label("Filter by User Status:"),
    dcc.Dropdown(
        id='user-status-dropdown',
        options=status_options,
        value='All',
        placeholder="Select User Status"
    ),

    dcc.Graph(id='user-status-chart'),

    html.Button("Export  Users", id='export-button', n_clicks=0),
    dcc.Download(id="download-user-data")
])

# ----------------- Callbacks -----------------

# Update User Status Chart
'''@app.callback(
    Output('user-status-chart', 'figure'),
    [Input('state-dropdown', 'value'),
     Input('user-status-dropdown', 'value')]
)
def update_user_chart(selected_state, selected_status):
    filtered_users = user_data.copy()
    
    if selected_state:
        filtered_users = filtered_users[filtered_users['user_id'].isin(
            appointment[appointment['state'] == selected_state]['user_id']
        )]
    
    if selected_status != 'All':
        filtered_users = filtered_users[filtered_users['user_status'] == selected_status]

    # Show top 50 users
    top_users = filtered_users.sort_values(by='days_since_last_appointment', ascending=True)
    
    return px.bar(
        top_users,
        x='email',
        y='days_since_last_appointment',
        color='user_status',
        title="Users by Status",
        labels={'email': 'User Email', 'days_since_last_appointment': 'Days Since Last Appointment'}
    )
'''

#Update chart 

# Update User Status Chart
@app.callback(
    Output('user-status-chart', 'figure'),
    [Input('state-dropdown', 'value'),
     Input('user-status-dropdown', 'value')]
)
def update_user_chart(selected_state, selected_status):
    # Filter user data
    filtered_users = user_data.copy()
    
    if selected_state:
        filtered_users = filtered_users[filtered_users['user_id'].isin(
            appointment[appointment['state'] == selected_state]['user_id']
        )]
    
    if selected_status != 'All':
        filtered_users = filtered_users[filtered_users['user_status'] == selected_status]

    # Aggregate counts by user status
    status_counts = filtered_users['user_status'].value_counts().reset_index()
    status_counts.columns = ['user_status', 'count']
    
    # Ensure all statuses are included even if missing in filter
    for status in ['Potential', 'Inactive (6 Months)', 'Lost', 'Recurring', 'No Appointments']:
        if status not in status_counts['user_status'].values:
            status_counts = pd.concat([status_counts, pd.DataFrame({'user_status': [status], 'count': [0]})])
    
    status_counts = status_counts.sort_values(by='user_status').reset_index(drop=True)
    
    # Plot aggregated bar chart
    return px.bar(
        status_counts,
        x='user_status',
        y='count',
        color='user_status',
        title="User Distribution by Status",
        labels={'user_status': 'User Status', 'count': 'User Count'}
    )


# Export Top Users
@app.callback(
    Output("download-user-data", "data"),
    [Input('export-button', 'n_clicks'),
     Input('state-dropdown', 'value'),
     Input('user-status-dropdown', 'value')]
)
def export_user_data(n_clicks, selected_state, selected_status):
    if n_clicks > 0:
        # Apply filters directly on appointment to reduce data size early
        filtered_appointments = appointment.copy()
        
        if selected_state:
            filtered_appointments = filtered_appointments[filtered_appointments['state'] == selected_state]
        
        if selected_status != 'All':
            user_ids = user_data[user_data['user_status'] == selected_status]['user_id']
            filtered_appointments = filtered_appointments[filtered_appointments['user_id'].isin(user_ids)]
        
        # Group data by user_id
        grouped_appointments = filtered_appointments.groupby('user_id')
        
        # Parallel processing for detailed export data
        def process_user_data(user_id, group):
            return {
                'user_id': user_id,
                'g_ids': ', '.join(group['g_id'].unique().astype(str)),
                'total_appointments': group['appointment_id'].count(),
                'appointment_dates': ', '.join(group['appointment_date'].dt.strftime('%Y-%m-%d %H:%M')),
                'Appointment_status': ', '.join(group['status']),
                'user_status': group['user_status'].iloc[0] if 'user_status' in group.columns else 'Unknown',
                'state': group['state'].iloc[0] if 'state' in group.columns else 'Unknown',
                'total_final_sum': group['total_final'].sum()
        }

from joblib import Parallel, delayed
import multiprocessing

# ----------------- Optimized Export Callback -----------------

# Export Detailed User Data with Parallel Processing
@app.callback(
    Output("download-user-data", "data"),
    [Input('export-button', 'n_clicks'),
     Input('state-dropdown', 'value'),
     Input('user-status-dropdown', 'value')]
)
def export_user_data(n_clicks, selected_state, selected_status):
    if n_clicks > 0:
        # Apply filters directly on appointment to reduce data size early
        filtered_appointments = appointment.copy()
        
        if selected_state:
            filtered_appointments = filtered_appointments[filtered_appointments['state'] == selected_state]
        
        if selected_status != 'All':
            user_ids = user_data[user_data['user_status'] == selected_status]['user_id']
            filtered_appointments = filtered_appointments[filtered_appointments['user_id'].isin(user_ids)]
        
        # Group data by user_id
        grouped_appointments = filtered_appointments.groupby('user_id')
        
        # Parallel processing for detailed export data
        def process_user_data(user_id, group):
            return {
                'user_id': user_id,
                'g_ids': ', '.join(group['g_id'].unique().astype(str)),
                'total_appointments': group['appointment_id'].count(),
                'appointment_dates': ', '.join(group['appointment_date'].dt.strftime('%Y-%m-%d %H:%M')),
                'Appointment_status': ', '.join(group['status']),
                'user_status': group['user_status'].iloc[0] if 'user_status' in group.columns else 'Unknown',
                'state': group['state'].iloc[0] if 'state' in group.columns else 'Unknown',
                'total_final_sum': group['total_final'].sum()
            }
        
        # Determine number of available CPU cores
        num_cores = multiprocessing.cpu_count()
        
        detailed_data = Parallel(n_jobs=num_cores)(
            delayed(process_user_data)(user_id, group) for user_id, group in grouped_appointments
        )
        
        # Create a DataFrame from parallel results
        export_df = pd.DataFrame(detailed_data)
        
        return dcc.send_data_frame(
            export_df.to_csv,
            filename="detailed_user_data.csv",
            index=False
        )

if __name__ == '__main__':
    app.run_server(port='8051',debug=True)
