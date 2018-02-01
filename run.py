from scholarship_graph.app import app
from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_simple

def simple(env, resp):
    resp(b'200 OK', [('Content-Type', b'text/plain')])
    return [b'SCHOLARSHIP GRAPH']

parent_app = DispatcherMiddleware(
    simple,
    {"/scholarship-graph": app})

if app.config.get("DEBUG") is True:
   parent_app.debug = True

if __name__ == "__main__":
    print("Running Scholarship Graph Application in Development Mode")
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.run(host='0.0.0.0', port=7225, debug=True)
