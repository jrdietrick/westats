import json
from renderers import template_env


class HighchartRenderer(object):

    def __init__(self, highchart_data):
        self.highchart_data = highchart_data

    def render(self):
        return template_env.get_template('highchart.haml').render({'chart_json': json.dumps(self.highchart_data)})
