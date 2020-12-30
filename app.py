import base64
import io
from os import getenv
from os.path import join, dirname

import dash
import dash_auth
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import pandas as pd
from dash.dependencies import Input, Output, State
from dotenv import load_dotenv
from jinja2 import Template
import phonenumbers

from twilio_client import TwilioClient

# Load .env variable
load_dotenv(join(dirname(__file__), '.env'))

COL_NAMES = ['first_name', 'last_name', 'phone_number']

app = dash.Dash('Bulk SMS', external_stylesheets=[dbc.themes.COSMO])
auth = dash_auth.BasicAuth(app, {getenv("USERNAME"): getenv("PASSWORD")})
twilio_client = TwilioClient(app.server)

sidebar = html.Div(
    style={
        "position": "fixed",
        "top": 0,
        "left": 0,
        "bottom": 0,
        "width": "20rem",
        "padding": "2rem 1rem",
        "background-color": "#f8f9fa",
    },
    children=[
        html.H2("Bulk SMS", className="display-4"),
        html.Hr(),
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select Files')
            ]),
            style={
                'width': '95%',
                'height': '60px',
                'lineHeight': '60px',
                'borderWidth': '1px',
                'borderStyle': 'dashed',
                'borderRadius': '5px',
                'textAlign': 'center',
                'margin': '10px',
                'font-size': '0.9rem'
            },
            multiple=False
        ),
        html.Br(),
        html.H4('Required column names:', style={'font-weight': 'bold'}),
        html.H5('first_name'),
        html.H5('last_name'),
        html.H5('phone_number'),
    ],
)

content = html.Div(
    id="page-content",
    style={
        "margin-left": "20rem",
        "margin-right": "2rem",
        "padding": "2rem 1rem",
        "margin-top": "2rem",
    },
    children=[
        dbc.Row([
            dbc.Col(
                id='data-table',
                width=8,
                children=dash_table.DataTable(id='table'),
            ),
            dbc.Col(
                children=[
                    html.Div([
                        dbc.Label("What message would you like to send?"),
                        html.Br(),
                        dbc.Textarea(id='input-text', placeholder="Hey {{first_name}} what's going on?", bs_size='md'),
                        dbc.FormText("Use squiggly brackets to insert a field from the table. e.g. {{first_name}}"),
                        html.Br(),
                        dbc.Input(id='image-url', placeholder="Image URL to send", bs_size="md", type='url'),
                        dbc.FormText(
                            ["Use ", html.A("https://imgur.com/upload", href="https://imgur.com/upload", target="_blank"),
                             " to generate a URL for your image."]
                        ),
                    ]),
                    html.Hr(),
                    html.Div(id='message-preview', style={'margin-top': '2rem'}),
                    html.Hr(),
                    html.Br(),
                    dbc.Button("Send Messages", id="open-send-confirm", color="primary", size="lg"),
                    html.A(
                        dbc.Button(
                            "Reset All", id="reset-all-button", color="secondary",
                            size="lg", style={'marginLeft': '20px'}
                        ),
                        href='/'
                    ),
                ],
                width=4
            )
        ]),
    ],
)

app.layout = html.Div([
    sidebar,
    content,
    dbc.Modal(
        [
            dbc.ModalHeader("Are you sure you want to send?"),
            dbc.ModalBody(id='confirm-modal-body'),
            dbc.ModalFooter([
                dbc.Button("Send", id="confirm-send", color="success"),
                dbc.Button("Cancel", id="cancel-send", color="danger"),
            ]),
        ],
        id="send-confirm-modal",
    ),
    dbc.Spinner(html.Div(id="loading-output"), fullscreen=True, size='lg',
                fullscreen_style={'backgroundColor': 'rgba(0, 0, 0, 0.14)'}),
    dcc.Store(id='send-data-store'),
])


# Data Upload into the table
@app.callback(Output('data-table', 'children'),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'))
def update_table(contents, filename):
    df = pd.DataFrame(columns=COL_NAMES)
    if contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            if 'csv' in filename:
                # Assume that the user uploaded a CSV file
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            elif 'xls' in filename:
                # Assume that the user uploaded an excel file
                df = pd.read_excel(io.BytesIO(decoded))
            else:
                return html.Div([
                    'Unsupported content type ' + content_type
                ], className="text-danger")
            df = df[COL_NAMES]
            df = df.dropna()
        except Exception as e:
            return html.Div([
                'There was an error processing this file: ' + str(e)
            ], className="text-danger")
    return [
        html.H4(filename, style={'font-weight': 'bold'}),
        dash_table.DataTable(
            id='table',
            columns=[{"name": i, "id": i} for i in df.columns],
            data=df.to_dict('records'),
            editable=False,
            page_size=50,
            style_cell={'textAlign': 'left', 'fontFamily': 'arial'},
            style_header={'fontWeight': 'bold', 'backgroundColor': 'rgb(230, 230, 230)'},
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': 'rgb(248, 248, 248)'
                }
            ],
        )
    ]


# Message preview
@app.callback(Output('message-preview', 'children'),
              [Input('image-url', 'value'),
               Input('input-text', 'value'),
               Input('table', 'data')])
def update_message_preview(img_url, text_value, data):
    if data and isinstance(data, list):
        data = data[0]
    if text_value and data:
        try:
            message = Template(text_value).render(**data)
        except Exception:
            message = text_value
    elif text_value and not data:
        message = text_value
    elif img_url and not text_value:
        message = ""
    else:
        return [html.H3('Message Preview')]
    return [
        html.H3('Message Preview'),
        html.Br(),
        html.Div(f'Phone Number: {data.get("phone_number")}') if data else None,
        html.Div(f'First Name: {data.get("first_name")}') if data else None,
        html.Div(f'Last Name: {data.get("last_name")}') if data else None,
        dbc.Card(
            [
                dbc.CardBody(message),
                dbc.CardImg(src=img_url, bottom=True) if img_url else None,
            ]
        )
    ]


# Modal to confirm that sending should occur
@app.callback(
    [Output("send-confirm-modal", "is_open"),
     Output('confirm-modal-body', 'children'),
     Output('confirm-send', 'disabled'),
     Output('send-data-store', 'data')],
    [Input("open-send-confirm", "n_clicks"),
     Input("cancel-send", "n_clicks"),
     Input("confirm-send", "n_clicks")],
    [State("send-confirm-modal", "is_open"),
     State('table', 'data')],
)
def confirm_sms_send(open_confirm, cancel_confirm, confirm, is_open, data):
    if data:
        msg = f"{len(data) if isinstance(data, list) else 1} messages will be sent"
        disabled = False
    else:
        msg = "No data uploaded. Unable to send anything"
        disabled = True
    if confirm and not disabled:
        return not is_open, msg, disabled, data
    elif open_confirm or cancel_confirm or confirm:
        return not is_open, msg, disabled, None
    return is_open, msg, disabled, None


@app.callback(
    [Output("loading-output", "children"),
     Output('table', 'data')],
    [Input("send-data-store", "data")],
    [State('table', 'data'),
     State('input-text', 'value'),
     State('image-url', 'value')]
)
def load_output(send_data, table_data, input_text, image_url):
    try:
        if send_data and input_text:
            if isinstance(send_data, dict):
                send_data = [send_data]
            for row in send_data:
                message = Template(input_text).render(**row)
                p = phonenumbers.parse(str(row['phone_number']), 'US')
                if phonenumbers.is_valid_number(p):
                    to = phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
                    twilio_client.send_message(
                        to=to,
                        message=message,
                        media_url=image_url if image_url else None
                    )
            toast = dbc.Toast(
                "Messages have been sent.",
                id="positioned-toast",
                header="Success",
                is_open=True,
                dismissable=True,
                icon="success",
                style={"position": "fixed", "top": 20, "right": 20, "width": 800},
                duration=4000,
            )
            return toast, None
        return None, table_data
    except Exception as e:
        toast = dbc.Toast(
            str(e),
            id="positioned-toast",
            header="Error",
            is_open=True,
            dismissable=True,
            icon="error",
            style={"position": "fixed", "top": 20, "right": 20, "width": 800},
        )
        return toast, None


if __name__ == "__main__":
    app.run_server(debug=True)
