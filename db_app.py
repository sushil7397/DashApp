import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.express as px
import datetime
import psycopg2
from sqlalchemy import create_engine
from datetime import datetime
import datetime
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
import pytz  # For timezone handling

# Create 'today' as tz-aware
today = pd.Timestamp.now(tz='UTC')
# Database configuration
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Retrieve database configuration from .env
DB_CONFIG = {
    'NAME': os.getenv('DB_NAME'),
    'USER': os.getenv('DB_USER'),
    'PASSWORD': os.getenv('DB_PASSWORD'),
    'HOST': os.getenv('DB_HOST'),
    'PORT': os.getenv('DB_PORT'),
}

# Create a database engine
db_url = f"postgresql://{DB_CONFIG['USER']}:{DB_CONFIG['PASSWORD']}@{DB_CONFIG['HOST']}:{DB_CONFIG['PORT']}/{DB_CONFIG['NAME']}"
engine = create_engine(db_url)

# Fetch data from database
def fetch_data(query):
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

# ----------------- Load Data -----------------
# Load appointment data

appointment = fetch_data("SELECT * FROM zip_appointment")

STATUS_MAPPING = {
    'N': 'Not Assigned',
    'D': 'Assigned',
    'O': 'On-the-Way',
    'W': 'In-Progress',
    'C': 'Cancelled',
    'S': 'Completed',
    'F': 'Failure',
    'R': 'Rejected',
    'L': 'Rescheduled',
    'P': 'Paid'
}
# Ensure appointment_date is in datetime format
appointment['appointment_date'] = pd.to_datetime(appointment['cdate'], format='%d-%m-%Y %H:%M', dayfirst=True)

# Convert user_id and g_id to string
appointment['user_id'] = appointment['user_id'].astype(str)
appointment['g_id'] = appointment['g_id'].astype(str)


appointment = appointment.copy() 
appointment = appointment.fillna({col: 0 for col in appointment.columns})


# Load user data
user = fetch_data("SELECT * FROM zip_user")
user['email'] = user.get('email', 'No Email')  # Ensure 'email' column exists
user['user_id'] = user['user_id'].astype(str)
user = user[['user_id', 'email']]

# Load address data
address = fetch_data("SELECT * FROM zip_address")

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
user_last_appointment['appointment_date'] = pd.to_datetime(
    user_last_appointment['appointment_date']
).dt.tz_convert(None)
user_last_appointment['days_since_last_appointment'] = (
    today - user_last_appointment['appointment_date']
).dt.days

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

user_last_appointment['status'] = user_last_appointment['days_since_last_appointment'].apply(classify_user)

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
            button.export {
            background-color: rgba(68, 68, 68, 0.7);
            border: 1px solid transparent;
            border-radius: 3px;
            box-shadow: rgba(255, 255, 255, .4) 0 1px 0 0 inset;
            box-sizing: border-box;
            color: #fff;

            cursor: pointer;
            display: inline-block;
            font-family: -apple-system,system-ui,"Segoe UI","Liberation Sans",sans-serif;
            font-size: 13px;
            font-weight: 400;
            line-height: 1.15385;
            margin: 10px 0;
            outline: none;
            padding: 8px .8em;
            position: relative;
            text-align: center;
            text-decoration: none;
            user-select: none;
            -webkit-user-select: none;
            touch-action: manipulation;
            vertical-align: baseline;
            white-space: nowrap;
            }

            button.export:hover,
            button.export:focus {
            background-color: #07c;
            }

            button.export:focus {
            box-shadow: 0 0 0 4px rgba(0, 149, 255, .15);
            }

            button.export:active {
            background-color: #0064bd;
            box-shadow: none;
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
            html.H2('Dashboard', style={'color': '#fff', 'text-align': 'center'}),  # Title with padding

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
                        html.I(className="fa fa-chart-bar", style={'font-size': '20px', 'margin-right': '10px'}),
                        'Total Final Summary'
                    ], style={'display': 'flex', 'align-items': 'center'}),
                    href='/final-summary',
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
                dcc.Link(
                    html.Div([
                        html.I(className="fa fa-clipboard-list", style={'font-size': '20px', 'margin-right': '10px'}),
                        'Registration Analysis'
                    ], style={'display': 'flex', 'align-items': 'center'}),
                    href='/registration',
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
address_mapped = fetch_data("SELECT * FROM zip_address_mapped")

address_mapped['user_id'] = address_mapped['user_id'].astype(str)
appointment = pd.merge(appointment, address_mapped[['user_id', 'state']], on='user_id', how='left')

# Rename the 'state_y' column to 'state' and drop the 'state_x' column
appointment['state'] = appointment['state_y']
appointment.drop(columns=['state_x', 'state_y'], inplace=True)

users = fetch_data("SELECT * FROM zip_user")

appointments = fetch_data("SELECT * FROM zip_appointment")

users['user_id'] = users['user_id'].astype(str)
appointments['user_id'] = appointments['user_id'].astype(str)
merged_data = pd.merge(appointments, users[['user_id', 'zip']], on='user_id', how='left')

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
        html.Div([
            html.H3("State-wise Revenue", style={'textAlign': 'center'}),
            dcc.Graph(id='state-revenue-chart'),
        ]),
        html.Div([
            html.H3("Complaints by G_ID", style={'textAlign': 'center'}),
            dcc.Graph(id='complaints-chart'),
        ]),

        html.Br(),
        # Heatmap
        html.Div([
            html.H3("Appointment Heatmap", style={'textAlign': 'center'}),
            dcc.Graph(id='appointment-heatmap'),  # Add the heatmap element here
        ]),
        html.Div([
            html.H3("G_ID Distribution Map", style={'textAlign': 'center'}),
            html.Div(id='google-map-chart'),  # Placeholder for Google Map chart
        ]),

        html.Br(),
    ])

import dash_leaflet as dl
import numpy as np
# Callback to update KPI, Appointment Summary, and Total Final Summary
@app.callback(
    [Output('home-kpis', 'children'),
     Output('appointment-summary-chart', 'figure'),
     Output('complaints-chart', 'figure'),
     Output('state-revenue-chart', 'figure'), 
      Output('appointment-heatmap', 'figure'),
      Output('google-map-chart', 'children')],
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_home_content(start_date, end_date):
    # Convert to datetime
    start_date = pd.to_datetime(start_date).tz_localize('UTC')
    end_date = pd.to_datetime(end_date).tz_localize('UTC')

    # Filter appointments based on date range
    filtered_data = appointment[
        (appointment['appointment_date'] >= start_date) &
        (appointment['appointment_date'] <= end_date)
    ]

    # Calculate KPIs
    total_appointments = filtered_data['appointment_id'].nunique()
    total_users = filtered_data['user_id'].nunique()
    avg_days_to_appointment = (filtered_data['appointment_date'].max() - filtered_data['appointment_date'].min()).days

    filtered_data['total_final'] = pd.to_numeric(filtered_data['total_final'], errors='coerce')
    print(filtered_data['total_final'].sum())
    total_revenue = filtered_data['total_final'].sum()
    print(filtered_data['total_final'].head())
    print(filtered_data['total_final'].sum())

    # Format total revenue to two decimal places
    total_revenue_formatted = f"{total_revenue:.2f}"
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
        html.Div([
            html.H3("Total Revenue"),
            html.P(f"${total_revenue_formatted}", style={'fontSize': '40px', 'color': 'green'})
        ], className="card"),
    ], style={'display': 'flex', 'justify-content': 'space-around'})


    # Appointment Summary Chart
    appointment_summary = filtered_data['status'].map(STATUS_MAPPING).value_counts().reset_index()
    appointment_summary.columns = ['Status', 'Count']

    chart = px.bar(
        appointment_summary,
        x='Status',
        y='Count',
        title='Summary of Appointments by Status',
        labels={'Status': 'Appointment Status', 'Count': 'Number of Appointments'},
        color='Status'
    )
    filtered_data['if_complain'] = filtered_data['if_complain'].map({'Yes': 1, 'No': 0}).fillna(0)

    # Filter for complaints where 'if_complain' equals 1
    complaints_data = (
        filtered_data[filtered_data['if_complain'] == 1]
        .groupby('g_id')
        .size()
        .reset_index(name='Complaint Count')
    )

    # Ensure there is data for the chart
    if complaints_data.empty:
        complaints_data = pd.DataFrame({'g_id': [], 'Complaint Count': []})

    # Generate a bar chart for complaints
    complaints_chart = px.bar(
        complaints_data,
        x='g_id',
        y='Complaint Count',
        title='Complaints by G_ID',
        labels={'g_id': 'G_ID', 'Complaint Count': 'Number of Complaints'},
        color='Complaint Count',  # Optional: Color the bars by complaint count
        height=600
    )

    # Customize chart layout
    complaints_chart.update_layout(
        xaxis_title="G_ID",
        yaxis_title="Number of Complaints",
        template="plotly_white",  # Use a clean and modern template
        coloraxis_showscale=False,  # Hide the color scale for simplicity
        font=dict(size=12),
    )

    state_revenue = filtered_data.groupby('state').agg(
        Revenue=('total_final', 'sum')  # Summing up the revenue by state
    ).reset_index()

    # Create a bar chart for revenue by state
    state_revenue_chart = px.bar(
        state_revenue,
        x='state',
        y='Revenue',
        title='State-wise Revenue',
        labels={'state': 'State', 'Revenue': 'Total Revenue'},
        color='Revenue',  # Optional: Color the bars by revenue
        height=600  # Optional: Adjust height for better visibility
    )

    # Customize the layout
    state_revenue_chart.update_layout(
        xaxis_title="State",
        yaxis_title="Total Revenue",
        template="plotly_white"  # Optional: Clean layout
    )
    
    # 1. G_ID Summary based on States and Total Final
    g_id_summary = filtered_data.groupby(['g_id', 'state']).agg(
        Revenue=('total_final', 'sum'), 
        Appointment_Count=('appointment_id', 'size')  # Count of appointments for each g_id and state
    ).reset_index()
    g_id_summary['Revenue'] = g_id_summary['Revenue'].apply(lambda x: f"{x:.2f}")
    # Update the DataTable to show Revenue and Appointment Count
    g_id_summary_table = dash.dash_table.DataTable(
        id='g-id-summary-table',
        columns=[
            {"name": "G_ID", "id": "g_id"},
            {"name": "State", "id": "state"},
            {"name": "Revenue", "id": "Revenue"},
            {"name": "Appointment Count", "id": "Appointment_Count"}
        ],
        data=g_id_summary.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'}
    )


    # 2. G_ID Complaints based on States
    if 'if_complain' in filtered_data.columns:
        filtered_data['if_complain'] = filtered_data['if_complain'].map({'Yes': 1, 'No': 0}).fillna(0)

    if 'if_complain' in filtered_data.columns and not filtered_data.empty:
        g_id_complaints = filtered_data[filtered_data['if_complain'] == 1].groupby(['g_id', 'state']).size().reset_index(name='Complaints')
    else:
        g_id_complaints = pd.DataFrame(columns=['G_ID', 'State', 'Complaints'])


    g_id_complaints_table = dash.dash_table.DataTable(
        id='g-id-complaints-table',
        columns=[{"name": col, "id": col} for col in g_id_complaints.columns],
        data=g_id_complaints.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'},
    )

    # 3. Total Count of Users by State
    user_state_count = filtered_data.groupby('state')['user_id'].nunique().reset_index()
    user_state_count.columns = ['State', 'User Count']
    user_state_count_table = dash.dash_table.DataTable(
        id='user-state-count-table',
        columns=[{"name": col, "id": col} for col in user_state_count.columns],
        data=user_state_count.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'}
    )

    heatmap_data = merged_data.groupby(['zip', 'g_id']).size().reset_index(name='Count')
    heatmap = px.density_heatmap(
        heatmap_data, x='zip', y='g_id', z='Count',
        title="Heatmap: G_IDs Close to Users by Zip Code",
        color_continuous_scale="Viridis"
    )


    state_names = {
        "AL": "Alabama",
        "AR": "Arkansas",
        "AZ": "Arizona",
        "NY": "New York",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DC": "District of Columbia",
        "DE": "Delaware",
        "FL": "Florida",
        "GA": "Georgia",
        "HI": "Hawaii",
        "IL": "Illinois",
        "IN": "Indiana",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "MA": "Massachusetts",
        "MD": "Maryland",
        "ME": "Maine",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MO": "Missouri",
        "MS": "Mississippi",
        "MT": "Montana",
        "NC": "North Carolina",
        "NE": "Nebraska",
        "NJ": "New Jersey",
        "NH": "New Hampshire",
        "NV": "Nevada",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "PA": "Pennsylvania",
        "SC": "South Carolina",
        "TX": "Texas",
        "TN": "Tennessee",
        "UT": "Utah",
        "VA": "Virginia",
        "WA": "Washington",
        "WY": "Wyoming",
    }
    new_filtered_data = pd.merge(filtered_data, address_mapped[['user_id', 'zip']], on='user_id', how='left')

    # Extract ZIP, Latitude, and Longitude
    zip_coordinates = (
        address_mapped.groupby('zip')[['latitude', 'longitude']]
        .mean()
        .dropna()  # Ensure no missing values
        .reset_index()
        .set_index('zip')
        .to_dict('index')
    )
    zip_coordinates = {
        zip_code: (coords['latitude'], coords['longitude'])
        for zip_code, coords in zip_coordinates.items()
    }

        # Process each ZIP and associated user_ids and g_ids
    zip_user_g_id_data = new_filtered_data.groupby('zip').agg({
        'user_id': list,
        'g_id': list
    }).reset_index()

    markers = []
    for zip_code, user_ids, g_ids in zip(zip_user_g_id_data['zip'], zip_user_g_id_data['user_id'], zip_user_g_id_data['g_id']):
        if zip_code in zip_coordinates:
            # Remove duplicates and filter out NaN values
            distinct_user_ids = sorted(set(filter(lambda x: x == x, user_ids)))  # Filter NaN and deduplicate
            distinct_g_ids = sorted(set(filter(lambda x: x == x, g_ids)))  # Filter NaN and deduplicate
            user_id_count = len(distinct_user_ids)

            # Get the state abbreviation from the ZIP code (assuming it's in address_mapped)
            state_abbr = address_mapped[address_mapped['zip'] == zip_code]['state'].iloc[0]  # Extract state abbreviation for the ZIP code
            state_name = state_names.get(state_abbr, 'Unknown State')  # Map state abbreviation to full state name

            # Prepare display strings for user_ids and g_ids
            if user_id_count == 0:
                user_ids_str = "No User_IDs available"
                g_ids_str = "No G_IDs available"
            else:
                user_ids_str = f"{user_id_count} User_ID(s): {', '.join(map(str, distinct_user_ids))}"
                g_ids_str = f"G_ID(s): {', '.join(map(str, distinct_g_ids))}"

            # Add marker to the list
            markers.append(
                dl.Marker(
                    position=zip_coordinates[zip_code],
                    children=[
                        dl.Popup(f"""
                        ZIP: {zip_code}
                        State: {state_name} 
                        User ID Count: {user_id_count}
                        user ids:{user_ids_str}
                        g_ids:{g_ids_str}
                        """)
                    ],
                )
            )

    # Create the map with ZIP code-based markers
    google_map_chart = dl.Map(
        children=[
            dl.TileLayer(),  # Base layer for the map
            dl.LayerGroup(markers),
        ],
        center=[37.0902, -95.7129],  # Center the map (US coordinates)
        zoom=4,
        style={'height': '600px', 'width': '100%'},
    )

    # Return the map along with other KPIs and charts
    return kpis, chart, complaints_chart, state_revenue_chart, heatmap, google_map_chart


# ----------------- Page 2: User Status Analysis -----------------
def user_status_page():
    return html.Div([
        html.H1("User Status Analysis", style={'textAlign': 'center'}),

        # Dropdown Filters
        html.Label("Filter by State:"),
        dcc.Dropdown(
            id='state-dropdown',
            options=[{'label': state, 'value': state} for state in appointment['state'].unique()],
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

        # Export Button
        html.Button('Export User Data', id='export-button', n_clicks=0),
        
        # Hidden Div to trigger download
        dcc.Download(id="download-user-data")
    ])


@app.callback(
    Output('user-status-chart', 'figure'),
    [Input('state-dropdown', 'value'),
     Input('user-status-dropdown', 'value')],
)
def update_user_chart(selected_state, selected_status):
    # Filter users based on the state dropdown
    filtered_users = user_data.copy()

    if selected_state:
        # Filter users by the selected state from the pre-merged data
        state_user_ids = appointment[appointment['state'] == selected_state]['user_id']
        filtered_users = filtered_users[filtered_users['user_id'].isin(state_user_ids)]

    # Filter by user status
    if selected_status != 'All':
        filtered_users = filtered_users[filtered_users['status'] == selected_status]

    # Count the user status occurrences
    status_counts = filtered_users['status'].value_counts().reset_index()
    status_counts.columns = ['status', 'count']

    # Create a bar chart
    return px.bar(
        status_counts,
        x='status',
        y='count',
        title="User Distribution by Status",
        labels={'status': 'User Status', 'count': 'User Count'}
    )
from joblib import Parallel, delayed
import multiprocessing
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
            user_ids = user_data[user_data['status'] == selected_status]['user_id']
            filtered_appointments = filtered_appointments[filtered_appointments['user_id'].isin(user_ids)]

        # Group data by user_id
        grouped_appointments = filtered_appointments.groupby('user_id')

        # Parallel processing for detailed export data
        # Updated function to process user data
        def process_user_data(user_id, group):
            # Count different user statuses
            status_counts = group['status'].value_counts().to_dict()
            count_p = status_counts.get('P', 0)  # Potential
            count_c = status_counts.get('C', 0)  # Confirmed
            count_l = status_counts.get('L', 0)  # Lost
            count_all = group['status'].nunique()  # Unique statuses in the group

            # Count unique g_ids
            unique_g_ids = len(group['g_id'].unique())

            return {
                'user_id': user_id,
                'g_ids': ', '.join(group['g_id'].unique().astype(str)),
                'unique_g_ids': unique_g_ids,  # New column
                'total_appointments': group['appointment_id'].count(),
                'appointment_dates': ', '.join(group['appointment_date'].dt.strftime('%Y-%m-%d %H:%M')),
                'Appointment_status': ', '.join(group['status']),
                'count_P': count_p,  # New column
                'count_C': count_c,  # New column
                'count_L': count_l,  # New column
                'count_All_Statuses': count_all,  # New column
                'status': group['status'].iloc[0] if 'status' in group.columns else 'Unknown',
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

        # Create a downloadable CSV
        return dcc.send_data_frame(
            export_df.to_csv,
            filename="detailed_user_data.csv",
            index=False
        )

# ----------------- Page 3: Total Final Summary -----------------

def total_final_summary_page():
    return html.Div([
        html.H1("Total Final Summary", style={'textAlign': 'center'}),

        # Date Picker Filter
        html.Label("Filter Appointments by Date:"),
        dcc.DatePickerRange(
            id='date-picker-range',
            start_date=appointment['appointment_date'].min().date(),
            end_date=appointment['appointment_date'].max().date(),
            display_format='YYYY-MM-DD',
            style={'margin-bottom': '20px'}
        ),

        # Total Final Summary Section
        html.Div(id='total-final-summary'),
    ])


@app.callback(
    [Output('total-final-summary', 'children')],
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_home_content(start_date, end_date):
    start_date = pd.to_datetime(start_date).tz_localize('UTC')
    end_date = pd.to_datetime(end_date).tz_localize('UTC')
    filtered_data = appointment[
        (appointment['appointment_date'] >= start_date) &
        (appointment['appointment_date'] <= end_date)
    ]

    total_final_summary_data = []

    # G_ID Summary Table
    g_id_summary = filtered_data.groupby(['g_id', 'state']).agg(
        Revenue=('total_final', 'sum'),
        Appointment_Count=('appointment_id', 'size')
    ).reset_index()
    total_final_summary_data.append(html.Div([
        html.H4("G_ID Summary", style={'textAlign': 'center'}),
        html.Button('Export G_ID Summary', id='export-table-g-id-summary', n_clicks=0),
        dcc.Download(id="download-table-g-id-summary"),
        dash.dash_table.DataTable(
            columns=[{"name": col, "id": col} for col in g_id_summary.columns],
            data=g_id_summary.to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'center',  # Center align all text
                'padding': '10px',     # Add padding for better spacing
                'fontFamily': 'Arial',  # Use a clean, professional font
                'fontSize': '14px'
            },
            style_header={
                'backgroundColor': '#4CAF50',  # Header background color
                'color': 'white',             # Header text color
                'fontWeight': 'bold',         # Bold header text
                'textAlign': 'center'         # Center align header text
            },
            style_data={
                'backgroundColor': '#f9f9f9',  # Data row background color
                'border': '1px solid #ddd',   # Cell borders
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},  # Apply styles to odd rows
                    'backgroundColor': '#f2f2f2',
                },
                {
                    'if': {'state': 'active'},  # Highlight the active row (hover or selection)
                    'backgroundColor': '#d1e7dd',
                    'border': '1px solid #0f5132',
                    'color': '#0f5132',
                }
            ],
        )
    ], style={'marginBottom': '30px'}))

    # G_ID Complaints Table
    filtered_data['if_complain'] = filtered_data['if_complain'].map({'Yes': 1, 'No': 0})
        
        # Filter for complaints (where 'if_complain' is 1)
    complaints_data = filtered_data[filtered_data['if_complain'] == 1]
    g_id_complaints = complaints_data.groupby(['g_id', 'state']).size().reset_index(name='Complaints')
    total_final_summary_data.append(html.Div([
        html.H4("G_ID Complaints", style={'textAlign': 'center'}),
        html.Button('Export G_ID Complaints', id='export-table-g-id-complaints', n_clicks=0),
        dcc.Download(id="download-table-g-id-complaints"),
        dash.dash_table.DataTable(
            columns=[{"name": col, "id": col} for col in g_id_complaints.columns],
            data=g_id_complaints.to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'center',  # Center align all text
                'padding': '10px',     # Add padding for better spacing
                'fontFamily': 'Arial',  # Use a clean, professional font
                'fontSize': '14px'
            },
            style_header={
                'backgroundColor': '#4CAF50',  # Header background color
                'color': 'white',             # Header text color
                'fontWeight': 'bold',         # Bold header text
                'textAlign': 'center'         # Center align header text
            },
            style_data={
                'backgroundColor': '#f9f9f9',  # Data row background color
                'border': '1px solid #ddd',   # Cell borders
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},  # Apply styles to odd rows
                    'backgroundColor': '#f2f2f2',
                },
                {
                    'if': {'state': 'active'},  # Highlight the active row (hover or selection)
                    'backgroundColor': '#d1e7dd',
                    'border': '1px solid #0f5132',
                    'color': '#0f5132',
                }
            ],
        )
    ], style={'marginBottom': '30px'}))

    # User State Count Table
    user_state_count = filtered_data.groupby('state')['user_id'].nunique().reset_index()
    user_state_count.columns = ['State', 'User Count']
    total_final_summary_data.append(html.Div([
        html.H4("User State Count", style={'textAlign': 'center'}),
        html.Button('Export User State Count', id='export-table-user-state-count', n_clicks=0),
        dcc.Download(id="download-table-user-state-count"),
        dash.dash_table.DataTable(
            columns=[{"name": col, "id": col} for col in user_state_count.columns],
            data=user_state_count.to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'center',  # Center align all text
                'padding': '10px',     # Add padding for better spacing
                'fontFamily': 'Arial',  # Use a clean, professional font
                'fontSize': '14px'
            },
            style_header={
                'backgroundColor': '#4CAF50',  # Header background color
                'color': 'white',             # Header text color
                'fontWeight': 'bold',         # Bold header text
                'textAlign': 'center'         # Center align header text
            },
            style_data={
                'backgroundColor': '#f9f9f9',  # Data row background color
                'border': '1px solid #ddd',   # Cell borders
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},  # Apply styles to odd rows
                    'backgroundColor': '#f2f2f2',
                },
                {
                    'if': {'state': 'active'},  # Highlight the active row (hover or selection)
                    'backgroundColor': '#d1e7dd',
                    'border': '1px solid #0f5132',
                    'color': '#0f5132',
                }
            ],
        )
    ], style={'marginBottom': '30px'}))

    return [html.Div(total_final_summary_data)]


@app.callback(
    Output("download-table-g-id-summary", "data"),
    [Input("export-table-g-id-summary", "n_clicks"),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def export_table_g_id_summary(n_clicks, start_date, end_date):
    if n_clicks > 0:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        filtered_data = appointment[
            (appointment['appointment_date'] >= start_date) &
            (appointment['appointment_date'] <= end_date)
        ]
        g_id_summary = filtered_data.groupby(['g_id', 'state']).agg(
            Revenue=('total_final', 'sum'),
            Appointment_Count=('appointment_id', 'size')
        ).reset_index()
        return dcc.send_data_frame(g_id_summary.to_csv, filename="g_id_summary_table.csv", index=False)


@app.callback(
    Output("download-table-g-id-complaints", "data"),
    [Input("export-table-g-id-complaints", "n_clicks"),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def export_table_g_id_complaints(n_clicks, start_date, end_date):
    if n_clicks > 0:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        # Filter appointments within the date range
        filtered_data = appointment[
            (appointment['appointment_date'] >= start_date) &
            (appointment['appointment_date'] <= end_date)
        ]
        
        # Map 'Yes' to 1 and 'No' to 0 in the 'if_complain' column
        filtered_data['if_complain'] = filtered_data['if_complain'].map({'Yes': 1, 'No': 0})
        
        # Filter for complaints (where 'if_complain' is 1)
        complaints_data = filtered_data[filtered_data['if_complain'] == 1]
        
        # Group by 'g_id' and 'state', then count complaints
        g_id_complaints = complaints_data.groupby(['g_id', 'state']).size().reset_index(name='Complaints')
        
        # Return CSV for download
        return dcc.send_data_frame(g_id_complaints.to_csv, filename="g_id_complaints_table.csv", index=False)


@app.callback(
    Output("download-table-user-state-count", "data"),
    [Input("export-table-user-state-count", "n_clicks"),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def export_table_user_state_count(n_clicks, start_date, end_date):
    if n_clicks > 0:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        filtered_data = appointment[
            (appointment['appointment_date'] >= start_date) &
            (appointment['appointment_date'] <= end_date)
        ]
        user_state_count = filtered_data.groupby('state')['user_id'].nunique().reset_index()
        user_state_count.columns = ['State', 'User Count']
        return dcc.send_data_frame(user_state_count.to_csv, filename="user_state_count_table.csv", index=False)

# ----------------- Page 4: Appointment Analysis -----------------
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
        dcc.Graph(id='average-days-to-appointment-line')
    ])

@app.callback(
    [Output('days-to-appointment-histogram', 'figure'),
     Output('average-days-to-appointment-line', 'figure')],
    Input('appointment-date-picker', 'start_date'),
    Input('appointment-date-picker', 'end_date')
)
def update_appointment_graphs(start_date, end_date):
    start_date = pd.to_datetime(start_date).tz_localize('UTC')
    end_date = pd.to_datetime(end_date).tz_localize('UTC')
    filtered_data = appointment[
        (appointment['appointment_date'] >= start_date) &
        (appointment['appointment_date'] <= end_date)
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


# ----------------- Page 4: Registration Analysis -----------------
user['registered_date'] = pd.to_datetime(appointment['cdate'], format='%d-%m-%Y %H:%M', dayfirst=True)
appointment = appointment.merge(user[['user_id', 'registered_date']], on='user_id', how='left')

appointment['days_to_appointment'] = (appointment['appointment_date'] - appointment['registered_date']).dt.days

appointment = appointment[appointment['days_to_appointment'].notnull() & (appointment['days_to_appointment'] >= 0)]
appointment['appointment_index'] = appointment.groupby('user_id').cumcount() + 1
appointment = appointment.sort_values(by=['user_id', 'appointment_date'])
appointment['days_between_appointments'] = appointment.groupby('user_id')['appointment_date'].diff().dt.days
appointment_gap_summary = (
    appointment
    .groupby('appointment_index')
    .agg(
        avg_days_between_appointments=('days_between_appointments', 'mean'),
        appointment_count=('appointment_id', 'count')
    )
    .reset_index()
)

def registrations():
    return html.Div([
    html.H1("Registration & Consecutive Appointment Analysis", style={'textAlign': 'center'}),

    # Dropdown to filter by Registration Quarter
    html.Label("Select Registration Quarter:"),
    dcc.Dropdown(
        id='quarter-dropdown',
        options=[
            {'label': str(quarter), 'value': str(quarter)}
            for quarter in appointment['registered_date'].dt.to_period('Q').unique()
        ],
        value=None,
        placeholder="Select a Quarter"
    ),

    # Graph for Days to Appointment Distribution
    dcc.Graph(id='days-of-appointment-histogram'),

    # Graph for Average Days to Appointment Over Quarters
    dcc.Graph(id='avg-days-to-appointment-line'),

    # Graph for Consecutive Appointment Gaps
    dcc.Graph(id='avg-days-between-appointments-line'),

    # Display Aggregated Metrics
    html.Div(id='appointment-gap-metrics', style={'margin-top': '20px', 'textAlign': 'center'})
])
@app.callback(
    [
        Output('days-of-appointment-histogram', 'figure'),
        Output('avg-days-to-appointment-line', 'figure'),
        Output('avg-days-between-appointments-line', 'figure'),
        Output('appointment-gap-metrics', 'children')
    ],
    [Input('quarter-dropdown', 'value')]
)
def update_all_figures(selected_quarter):
    # Filter data based on selected quarter
    filtered_data = (
        appointment[appointment['registered_date'].dt.to_period('Q') == selected_quarter]
        if selected_quarter
        else appointment
    )

    # Create histogram
    histogram_fig = px.histogram(
        filtered_data,
        x='days_to_appointment',
        nbins=30,
        title="Distribution of Days Between Registration and Appointment",
        color_discrete_sequence=['#636EFA']
    )

    # Create line chart for average days to appointment
    avg_days_summary = (
        filtered_data
        .groupby(filtered_data['registered_date'].dt.to_period('M'))
        .agg(avg_days_to_appointment=('days_to_appointment', 'mean'))
        .reset_index()
    )
    avg_days_fig = px.line(
        avg_days_summary,
        x=avg_days_summary['registered_date'].dt.to_timestamp(),  # Ensure compatibility
        y='avg_days_to_appointment',
        title="Average Days to Appointment Over Time",
        markers=True
    )

    # Create line chart for gaps between appointments
    gap_fig = px.line(
        appointment_gap_summary,
        x='appointment_index',
        y='avg_days_between_appointments',
        title='Average Days Between Consecutive Appointments',
        markers=True
    )

    # Display metrics
    avg_gap = filtered_data['days_to_appointment'].mean()
    total_appointments = filtered_data['appointment_id'].nunique()
    total_customers = filtered_data['user_id'].nunique()
    metrics = f"Avg Days to Appointment: {avg_gap:.2f} | Total Appointments: {total_appointments} | Total Customers: {total_customers}"

    return histogram_fig, avg_days_fig, gap_fig, metrics

# ----------------- Page Callback -----------------
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/user-status':
        return user_status_page()
    elif pathname == '/final-summary':
        return total_final_summary_page()
    elif pathname == '/appointment-analysis':
        return appointment_analysis_page()
    elif pathname == '/registration':
        return registrations()
    else:
        return home_page()

# ----------------- Run the App -----------------
if __name__ == '__main__':
    app.run_server(host='70.36.107.109',debug=True)