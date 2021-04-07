from flask import Flask, request, jsonify
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

@app.route('/')
def hello():
    return 'Hello, World!'

@app.route('/scoring-yolo', methods=['GET'])
def scoring():
    file_name = request.args["file_name"]
    return {
        'welcome': "Hello, %s" % file_name
    }

if __name__ == '__main__':
    app.run(debug=True)