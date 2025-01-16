import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.express as px
import datetime

# ----------------- Load Data -----------------
# Load appointment data
appointment = pd.read_csv(
    r'appointment_list.csv',
    low_memory=False
)

# Ensure appointment_date is in datetime format
appointment['appointment_date'] = pd.to_datetime(appointment['cdate'], format='%d-%m-%Y %H:%M', dayfirst=True)

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
user['email'] = user.get('email', 'No Email')  # Ensure 'email' column exists
user['user_id'] = user['user_id'].astype(str)
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
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Include FontAwesome CDN for icons in the head
app.index_string = '''
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''
# ----------------- URL Location -----------------
app.layout = html.Div([  
    dcc.Location(id='url', refresh=False),  # For page routing
    html.Div([  
        # Sidebar
        html.Div([  
            html.H2('Dashboard', style={'color': '#fff', 'text-align': 'center', 'padding': '20px 0'}),  # Title with padding

            html.Hr(style={'border': '1px solid #444', 'margin': '20px 0'}),  # Divider line for separation

            # Links as buttons with icons
            html.Div([  
                dcc.Link(
                    html.Div([
                        html.I(className="fa fa-home", style={'font-size': '20px', 'margin-right': '10px'}),
                        'Home'
                    ], style={'display': 'flex', 'align-items': 'center'}),
                    href='/',
                    style={'text-decoration': 'none', 'color': '#fff', 'padding': '12px 20px', 'border-radius': '5px', 'display': 'flex', 'width': '80%', 'background-color': '#555', 'margin-bottom': '10px'}
                ),

                dcc.Link(
                    html.Div([
                        html.I(className="fa fa-users", style={'font-size': '20px', 'margin-right': '10px'}),
                        'User Status Analysis'
                    ], style={'display': 'flex', 'align-items': 'center'}),
                    href='/user-status',
                    style={'text-decoration': 'none', 'color': '#fff', 'padding': '12px 20px', 'border-radius': '5px', 'display': 'flex', 'width': '80%', 'background-color': '#555', 'margin-bottom': '10px'}
                ),

                dcc.Link(
                    html.Div([
                        html.I(className="fa fa-calendar-check", style={'font-size': '20px', 'margin-right': '10px'}),
                        'Appointment Analysis'
                    ], style={'display': 'flex', 'align-items': 'center'}),
                    href='/appointment-analysis',
                    style={'text-decoration': 'none', 'color': '#fff', 'padding': '12px 20px', 'border-radius': '5px', 'display': 'flex', 'width': '80%', 'background-color': '#555', 'margin-bottom': '10px'}
                ),
            ], style={'margin-top': '30px'}),  # Adding margin-top to space out links
        ], style={
            'backgroundColor': '#333',  # Sidebar color
            'padding': '20px',  # Padding around the content
            'height': '100vh',  # Full-height sidebar
            'width': '250px',  # Sidebar width
            'position': 'fixed',  # Fixed position on the left
            'top': 0,  # Aligned to the top
            'left': 0,  # Aligned to the left
            'color': 'white',  # Text color
            'box-shadow': '2px 0px 5px rgba(0,0,0,0.2)'  # Adding shadow to the sidebar
        }),

        # Content Area
        html.Div(id='page-content', style={'margin-left': '320px', 'padding': '20px'}),  # Adjusted for new sidebar width
    ])
])


# ----------------- Home Page -----------------
# Load and prepare address data
address_mapped = pd.read_csv(r'address_mapped.csv', low_memory=False)
address_mapped['user_id'] = address_mapped['user_id'].astype(str)
appointment = pd.merge(appointment, address_mapped[['user_id', 'state']], on='user_id', how='left')

def home_page():
    return html.Div([
        html.H1("Dashboard Overview", style={'textAlign': 'center'}),

        # Date Picker Filter
        html.Label("Filter Appointments by Date:"),
        dcc.DatePickerRange(
            id='date-picker-range',
            start_date=appointment['appointment_date'].min().date(),
            end_date=appointment['appointment_date'].max().date(),
            display_format='YYYY-MM-DD',
            style={'margin-bottom': '20px'}
        ),

        # KPI Cards
        html.Div(id='home-kpis'),

        html.Br(),

        # Appointment Summary Chart
        html.Div([
            html.H3("Appointment Summary", style={'textAlign': 'center'}),
            dcc.Graph(id='appointment-summary-chart'),
        ]),

        html.Br(),

        # 360 Days Appointment Summary Table
        html.Div([
            html.H3("360 Days Appointment Summary", style={'textAlign': 'center'}),
            html.H4(id='summary-date-range', style={'textAlign': 'center'}),  # Display date range
            dash.dash_table.DataTable(
                id='summary-table',
                columns=[
                    {"name": "User ID", "id": "user_id"},
                    {"name": "State", "id": "state"},
                    {"name": "G ID", "id": "g_id"},
                    {"name": "Complaint", "id": "if_complain"},
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left'},
            )
        ])
    ])

# Callback for updating KPIs, Appointment Summary Chart, and Summary Table
@app.callback(
    [Output('home-kpis', 'children'),
     Output('appointment-summary-chart', 'figure'),
     Output('summary-table', 'data'),
     Output('summary-date-range', 'children')],  # Output for the dynamic date range
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_home_content(start_date, end_date):
    # Convert to datetime
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    # Filter appointments based on date range
    filtered_data = appointment[
        (appointment['appointment_date'] >= start_date) &
        (appointment['appointment_date'] <= end_date)
    ]

    # Calculate KPIs
    total_appointments = filtered_data['appointment_id'].nunique()
    total_users = filtered_data['user_id'].nunique()
    avg_days_to_appointment = (filtered_data['appointment_date'].max() - filtered_data['appointment_date'].min()).days

    kpis = html.Div([
        html.Div([
            html.H3("Total Appointments"),
            html.P(f"{total_appointments}", style={'fontSize': '40px'})
        ], className="card"),

        html.Div([
            html.H3("Total Users"),
            html.P(f"{total_users}", style={'fontSize': '40px'})
        ], className="card"),

        html.Div([
            html.H3("Avg Days to Appointment"),
            html.P(f"{avg_days_to_appointment}", style={'fontSize': '40px'})
        ], className="card"),
    ], style={'display': 'flex', 'justify-content': 'space-around'})

    # Appointment Summary Chart
    appointment_summary = filtered_data['status'].value_counts().reset_index()
    appointment_summary.columns = ['Status', 'Count']

    chart = px.bar(
        appointment_summary,
        x='Status',
        y='Count',
        title='Summary of Appointments by Status',
        labels={'Status': 'Appointment Status', 'Count': 'Number of Appointments'},
        color='Status'
    )

    # 360 Days Appointment Summary
    today = pd.Timestamp.now()
    last_360_days = today - pd.Timedelta(days=360)
    print(f"Last 360 days Date: {last_360_days}")

    # Filter appointments for the last 360 days
    recent_appointments = appointment[appointment['appointment_date'] >= last_360_days]
    summary_data = recent_appointments.merge(address_mapped, on='user_id', how='left')[['user_id', 'state', 'g_id', 'if_complain']]

    # Update 'if_complain' to Yes/No
    summary_data['if_complain'] = summary_data['if_complain'].apply(lambda x: 'Yes' if x == 1 else 'No')
    summary_data = summary_data.drop_duplicates()

    # Format the date range for the 360 Days Appointment Summary
    formatted_start_date = last_360_days.strftime('%Y-%m-%d')
    formatted_end_date = today.strftime('%Y-%m-%d')
    date_range_text = f"({formatted_start_date} to {formatted_end_date})"

    return kpis, chart, summary_data.to_dict('records'), date_range_text


# ----------------- Page 2: User Status Analysis -----------------
appointment_with_state = pd.merge(appointment, address_mapped[['user_id', 'state']], on='user_id', how='left')

def user_status_page():
    return html.Div([
        html.H1("User Status Analysis", style={'textAlign': 'center'}),

        # Dropdown Filters
        html.Label("Filter by State:"),
        dcc.Dropdown(
            id='state-dropdown',
            options=[{'label': state, 'value': state} for state in appointment_with_state['state'].unique()],
            value=None,
            placeholder="Select a state"
        ),

        html.Label("Filter by User Status:"),
        dcc.Dropdown(
            id='user-status-dropdown',
            options=[{'label': status, 'value': status} for status in ['All', 'Potential', 'Inactive (6 Months)', 'Lost', 'Recurring']],
            value='All',
            placeholder="Select User Status"
        ),

        # User Status Distribution Chart
        dcc.Graph(id='user-status-chart'),
    ])

@app.callback(
    Output('user-status-chart', 'figure'),
    [Input('state-dropdown', 'value'),
     Input('user-status-dropdown', 'value')]
)
def update_user_chart(selected_state, selected_status):
    # Filter users based on the state dropdown
    filtered_users = user_data.copy()

    if selected_state:
        # Filter users by the selected state from the pre-merged data
        state_user_ids = appointment_with_state[appointment_with_state['state'] == selected_state]['user_id']
        filtered_users = filtered_users[filtered_users['user_id'].isin(state_user_ids)]

    # Filter by user status
    if selected_status != 'All':
        filtered_users = filtered_users[filtered_users['user_status'] == selected_status]

    # Count the user status occurrences
    status_counts = filtered_users['user_status'].value_counts().reset_index()
    status_counts.columns = ['user_status', 'count']

    # Create a bar chart
    return px.bar(
        status_counts,
        x='user_status',
        y='count',
        title="User Distribution by Status",
        labels={'user_status': 'User Status', 'count': 'User Count'}
    )

# ----------------- Page 3: Appointment Analysis -----------------
def appointment_analysis_page():
    return html.Div([
        html.H1("Appointment Analysis", style={'textAlign': 'center'}),
        
        # Date Picker Filter
        html.Label("Filter Appointments by Date:"),
        dcc.DatePickerRange(
            id='appointment-date-picker',
            start_date=appointment['appointment_date'].min().date(),
            end_date=appointment['appointment_date'].max().date(),
            display_format='YYYY-MM-DD',
            style={'margin-bottom': '20px'}
        ),

        # Graphs
        dcc.Graph(id='days-to-appointment-histogram'),
        dcc.Graph(id='avg-days-to-appointment-line')
    ])

@app.callback(
    [Output('days-to-appointment-histogram', 'figure'),
     Output('avg-days-to-appointment-line', 'figure')],
    Input('appointment-date-picker', 'start_date'),
    Input('appointment-date-picker', 'end_date')
)
def update_appointment_graphs(start_date, end_date):
    filtered_data = appointment[
        (appointment['appointment_date'] >= pd.to_datetime(start_date)) &
        (appointment['appointment_date'] <= pd.to_datetime(end_date))
    ]

    histogram_fig = px.histogram(
        filtered_data,
        x='appointment_date',
        nbins=30,
        title="Days to Appointment Distribution"
    )

    avg_days_summary = (
        filtered_data.groupby('appointment_date')
        .size()
        .reset_index(name='count')
    )

    line_fig = px.line(
        avg_days_summary,
        x='appointment_date',
        y='count',
        title="Appointment Trends Over Time"
    )

    return histogram_fig, line_fig

# ----------------- Page Callback -----------------
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/user-status':
        return user_status_page()
    elif pathname == '/appointment-analysis':
        return appointment_analysis_page()
    else:
        return home_page()

# ----------------- Run the App -----------------
if __name__ == '__main__':
    app.run_server(debug=True)
