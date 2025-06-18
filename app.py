from flask import Flask, request, jsonify
from solution_creator import SolutionCreator
from flask_cors import CORS  # Import CORS



app = Flask(__name__)
CORS(app)

@app.post('/api') 
def api():
    query = request.get_json()
    sc = SolutionCreator()
    solution = sc.create_solution(query)
    return jsonify(solution)


if __name__ ==  '__main__':
    app.run()
