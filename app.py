from flask import Flask, request, jsonify
from solution_creator import SolutionCreator


app = Flask(__name__)



@app.get('/')
def index():
    return 'This app is working, send a post request to /api endpoint to use it.'

@app.post('/api') 
def api():
    query = request.get_json()
    sc = SolutionCreator()
    solution = sc.create_solution(query)
    return jsonify(solution)


if __name__ ==  '__main__':
    app.run(debug=True)