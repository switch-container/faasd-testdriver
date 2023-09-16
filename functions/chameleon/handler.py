from time import time
import six
import json
from chameleon import PageTemplate

# {
#     "num_of_rows": 1000,
#     "num_of_cols": 1000
# }


BIGTABLE_ZPT = """\
<table xmlns="http://www.w3.org/1999/xhtml"
xmlns:tal="http://xml.zope.org/namespaces/tal">
<tr tal:repeat="row python: options['table']">
<td tal:repeat="c python: row.values()">
<span tal:define="d python: c + 1"
tal:attributes="class python: 'column-' + %s(d)"
tal:content="python: d" />
</td>
</tr>
</table>""" % six.text_type.__name__


def handle(req):
    req = json.loads(req)
    num_of_rows = req['num_of_rows']
    num_of_cols = req['num_of_cols']

    start = time()
    tmpl = PageTemplate(BIGTABLE_ZPT)

    data = {}
    for i in range(num_of_cols):
        data[str(i)] = i

    table = [data for x in range(num_of_rows)]
    options = {'table': table}

    data = tmpl.render(options=options)
    latency = time() - start

    return {'latency': latency, 'data': data}
