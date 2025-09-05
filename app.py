from flask import Flask, render_template, request, jsonify, session
import time
import random
import json
import os
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Use DynamoDB for cloud storage
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('addition-game-scores')

class AdditionGameWeb:
    def get_difficulty_range(self, level):
        ranges = {1: (1, 10), 2: (10, 50), 3: (50, 100), 4: (100, 500), 5: (500, 1000)}
        return ranges.get(min(level, 5), (1000, 5000))
    
    def rate_ability(self, correct, total):
        percentage = (correct / total) * 100
        if percentage >= 90: return "Excellent"
        elif percentage >= 75: return "Good"
        elif percentage >= 60: return "Average"
        elif percentage >= 40: return "Below Average"
        else: return "Needs Practice"

game = AdditionGameWeb()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_game():
    session['name'] = request.json['name']
    session['level'] = 1
    session['correct'] = 0
    session['start_time'] = time.time()
    return get_question()

@app.route('/question')
def get_question():
    level = session.get('level', 1)
    min_val, max_val = game.get_difficulty_range(level)
    a, b = random.randint(min_val, max_val), random.randint(min_val, max_val)
    
    session['current_a'] = a
    session['current_b'] = b
    session['question_start'] = time.time()
    
    return jsonify({'question': f'{a} + {b}', 'level': level})

@app.route('/answer', methods=['POST'])
def check_answer():
    answer = int(request.json['answer'])
    elapsed = time.time() - session['question_start']
    correct_answer = session['current_a'] + session['current_b']
    
    if elapsed > 10:
        return end_game("Time's up!")
    elif answer == correct_answer:
        session['correct'] += 1
        session['level'] += 1
        return jsonify({'correct': True, 'time': round(elapsed, 1)})
    else:
        return end_game(f"Wrong! Answer was {correct_answer}")

def end_game(message):
    correct = session['correct']
    total = session['level'] - 1
    
    if total > 0:
        rating = game.rate_ability(correct, total)
        score = correct * 100
        
        # Save to DynamoDB
        try:
            table.put_item(Item={
                'id': f"{session['name']}-{int(time.time())}",
                'name': session['name'],
                'score': score,
                'correct': correct,
                'total': total,
                'rating': rating,
                'date': datetime.now().isoformat()
            })
        except ClientError:
            pass  # Handle error silently
        
        return jsonify({
            'game_over': True,
            'message': message,
            'score': score,
            'correct': correct,
            'total': total,
            'rating': rating
        })
    
    return jsonify({'game_over': True, 'message': 'No questions answered!'})

@app.route('/leaderboard')
def leaderboard():
    try:
        response = table.scan()
        scores = sorted(response['Items'], key=lambda x: x['score'], reverse=True)[:10]
        return jsonify(scores)
    except ClientError:
        return jsonify([])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
