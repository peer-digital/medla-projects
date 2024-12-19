from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

def test_categorization():
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Test case data
    test_case = {
        'id': 'TEST-123',
        'title': 'Meddelande om vägledning avseende registerkontroller och nya beslut om placering i säkerhetsklass',
        'description': None,
        'location': '',
        'municipality': '',
        'case_type': None,
        'decision_summary': None
    }
    
    # Create the prompt
    prompt = f'''Analyze this industrial project and categorize it:

Title: {test_case['title']}
Description: {test_case['description']}
Location: {test_case['location']}, {test_case['municipality']}
Case Type: {test_case['case_type']}
Decision Summary: {test_case['decision_summary']}

Based on the above information, determine:
1. The primary category from: ['Energy', 'Manufacturing', 'Infrastructure', 'Resource Extraction', 'Other']
2. The most appropriate sub-category from the corresponding list
3. A confidence score (0-1)
4. Brief reasoning for the categorization

Format the response as a JSON object with keys:
- primary_category
- sub_category
- confidence
- reasoning'''

    print('Sending request to OpenAI API...')
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {
                'role': 'system',
                'content': 'You are an expert in categorizing industrial projects with a focus on green industry and environmental impact.'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ]
    )
    
    print('\nResponse from API:')
    content = response.choices[0].message.content
    print(content)
    
    try:
        parsed = json.loads(content)
        print('\nParsed JSON:')
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError as e:
        print('\nFailed to parse response as JSON:', str(e))

if __name__ == '__main__':
    test_categorization() 