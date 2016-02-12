import json
from renderers import template_env


class HighchartRenderer(object):

    def __init__(self, highchart_data):
        self.highchart_data = {
            'exporting': {
                'sourceWidth': 1280,
                'sourceHeight': 800,
            },
        }
        self.highchart_data.update(highchart_data)

    def render(self):
        return template_env.get_template('highchart.haml').render({'chart_json': json.dumps(self.highchart_data)})
