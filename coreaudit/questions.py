"""The short questions shown before the 'book a call' step. Answers feed lead routing."""
QUESTIONS = [
    {"id": "goals", "label": "What do you most want to change?", "type": "multi", "options": [
        ("leads", "Get more leads or inquiries"), ("conversions", "Turn more visitors into customers"),
        ("sales", "Increase sales or revenue"), ("visibility", "Show up better on Google and Maps"),
        ("message", "Make my message and offer clearer"), ("unsure", "Not sure yet")]},
    {"id": "weakest", "label": "Which part feels weakest to you?", "type": "single", "options": [
        ("C", "Client: who I serve"), ("O", "Offer: what I sell"), ("R", "Route: how people reach me"),
        ("E", "Engine: speed, tracking, Google"), ("unsure", "Not sure")]},
    {"id": "help", "label": "How would you like to fix it?", "type": "single", "options": [
        ("diy", "Show me what to do, I will do it"), ("dfy", "Do it for me"), ("unsure", "Not sure yet")]},
    {"id": "challenge", "label": "Anything specific you are struggling with? (optional)", "type": "text"},
]
