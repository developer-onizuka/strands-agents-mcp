from flask import Flask, request, render_template, Response, jsonify, make_response, abort
from agent_module3 import agent

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def index():
    return render_template("index.html")

@app.route("/text", methods=['GET', 'POST'])
def inference() :
    try:
        if request.method == 'GET':
            return agent(request.args.get('value'))
        elif request.method == 'POST':
            inputText = request.form['value']
            agentResponse = agent(inputText)
            return render_template("index.html", agentResponse=agentResponse, inputText=inputText)
        else:
            return abort(400)
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5000)
