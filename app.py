from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_cors import CORS
import os
import json
import csv
import io
from datetime import datetime
from dotenv import load_dotenv
from config import Config

# Force load environment variables at the very beginning
load_dotenv()

# Import our custom modules
from utils.resume_parser import ResumeParser
from utils.ai_matcher import AIMatcher
from utils.job_analyzer import JobAnalyzer
from utils.query_parser import NaturalLanguageQueryParser

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize our AI components with error handling
resume_parser = ResumeParser()

# Initialize AI components with both GROQ and Gemini API keys
groq_api_key = app.config.get('GROQ_API_KEY')
gemini_api_key = os.getenv('GEMINI_API_KEY') or app.config.get('GEMINI_API_KEY')

print(f"🔧 App: Gemini API key loaded: {gemini_api_key[:20] if gemini_api_key else 'None'}...")
print(f"🔧 App: GROQ API key loaded: {groq_api_key[:20] if groq_api_key else 'None'}...")

# Initialize AI components with proper API keys
try:
    # Use Gemini for our enhanced AI features
    ai_matcher = AIMatcher(api_key=gemini_api_key)
    job_analyzer = JobAnalyzer(api_key=gemini_api_key)
    print("✅ AI components initialized successfully")
except Exception as e:
    print(f"❌ Error initializing AI components: {e}")
    # Initialize with fallback (no API key)
    ai_matcher = AIMatcher()
    job_analyzer = JobAnalyzer()

# 🆕 Initialize PeopleGPT Query Parser
try:
    query_parser = NaturalLanguageQueryParser()
    print("✅ PeopleGPT Query Parser initialized successfully")
except Exception as e:
    print(f"❌ Error initializing PeopleGPT Query Parser: {e}")
    query_parser = None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

# 🆕 UPDATED: PeopleGPT Search Page
@app.route('/search')
def search_page():
    """
    PeopleGPT Search Page - Natural Language Candidate Search
    Built by Team Seeds! 🌱 for pranamya-jain
    
    Features:
    - Natural language query parsing
    - Chat-like search interface
    - Real-time IST timestamps
    - Query suggestions
    - AI-powered candidate matching
    
    Template: search_enhanced.html
    Current: 2025-05-31 19:00:54 UTC
    """
    return render_template('search_enhanced.html')

@app.route('/analytics')
def analytics_page():
    return render_template('analytics.html')

@app.route('/api/upload_resume', methods=['POST'])
def upload_resume():
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file type
        allowed_extensions = {'pdf', 'docx', 'doc'}
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            return jsonify({'error': 'Only PDF and DOCX files are supported'}), 400
        
        # Save uploaded file
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Parse resume
        parsed_data = resume_parser.parse_resume(filepath)
        
        if 'error' in parsed_data:
            return jsonify({'error': parsed_data['error']}), 400
        
        # Store in our simple database (JSON file for now)
        candidate_id = save_candidate(parsed_data, filename)
        
        return jsonify({
            'success': True,
            'candidate_id': candidate_id,
            'parsed_data': parsed_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search_candidates', methods=['POST'])
def search_candidates():
    try:
        data = request.get_json()
        job_description = data.get('job_description', '')
        filters = data.get('filters', {})
        
        if not job_description.strip():
            return jsonify({'error': 'Job description is required'}), 400
        
        # Load candidates from our database
        candidates = load_candidates()
        
        if not candidates:
            return jsonify({
                'success': True,
                'candidates': [],
                'total': 0,
                'message': 'No candidates found in database'
            })
        
        # Use AI to match candidates - now with enhanced AI or fallback
        matched_candidates = ai_matcher.match_candidates(
            job_description, 
            candidates, 
            filters
        )
        
        # Get parsed criteria for display
        parsed_criteria = ai_matcher.parse_natural_language_query(job_description)
        
        return jsonify({
            'success': True,
            'candidates': matched_candidates,
            'total': len(matched_candidates),
            'parsed_criteria': parsed_criteria,
            'ai_enabled': ai_matcher.ai_available,
            'searched_by': 'pranamya-jain',
            'search_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ' UTC'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 🆕 NEW: PeopleGPT Natural Language Query Parser API
@app.route('/api/parse_query', methods=['POST'])
def parse_natural_language_query():
    """
    PeopleGPT - Parse natural language search queries
    Built by Team Seeds! 🌱 for pranamya-jain
    """
    try:
        if not query_parser:
            return jsonify({
                'success': False,
                'error': 'PeopleGPT Query Parser not available'
            }), 500
            
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query is required'
            }), 400
        
        # Validate query
        validation = query_parser.validate_query(query)
        if not validation['valid']:
            return jsonify({
                'success': False,
                'error': validation['error']
            }), 400
        
        # Parse the query
        parsed_result = query_parser.parse_query(query)
        
        return jsonify({
            'success': True,
            'parsed_query': parsed_result,
            'examples': query_parser.get_query_examples(),
            'message': f'Query parsed successfully by pranamya-jain',
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ' UTC'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Query parsing failed: {str(e)}'
        }), 500

# 🆕 NEW: PeopleGPT Integrated Search API
@app.route('/api/peoplegpt_search', methods=['POST'])
def peoplegpt_search():
    """
    PeopleGPT - Natural language search with AI parsing and candidate matching
    """
    try:
        if not query_parser:
            return jsonify({
                'success': False,
                'error': 'PeopleGPT not available'
            }), 500
            
        data = request.get_json()
        natural_query = data.get('query', '').strip()
        
        if not natural_query:
            return jsonify({
                'success': False,
                'error': 'Natural language query is required'
            }), 400
        
        # Step 1: Parse natural language query
        parsed_result = query_parser.parse_query(natural_query)
        
        # Step 2: Load candidates
        candidates = load_candidates()
        
        if not candidates:
            return jsonify({
                'success': True,
                'candidates': [],
                'parsed_query': parsed_result,
                'total_found': 0,
                'search_summary': 'No candidates found in database',
                'message': 'Upload some resumes to start searching!'
            })
        
        # Step 3: Use AI matcher with parsed job description
        matched_candidates = ai_matcher.match_candidates(
            parsed_result['job_description'], 
            candidates, 
            parsed_result['filters']
        )
        
        return jsonify({
            'success': True,
            'candidates': matched_candidates,
            'parsed_query': parsed_result,
            'total_found': len(matched_candidates),
            'search_summary': f"Found {len(matched_candidates)} candidates matching your criteria",
            'original_query': natural_query,
            'searched_by': 'pranamya-jain',
            'search_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ' UTC',
            'ai_enabled': ai_matcher.ai_available and query_parser is not None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'PeopleGPT search failed: {str(e)}'
        }), 500

@app.route('/api/analyze_job', methods=['POST'])
def analyze_job():
    try:
        data = request.get_json()
        job_description = data.get('job_description', '')
        
        if not job_description.strip():
            return jsonify({'error': 'Job description is required'}), 400
        
        # Use our enhanced job analyzer
        analysis = job_analyzer.analyze_job_description(job_description)
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'ai_enabled': job_analyzer.ai_available
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_candidates')
def get_candidates():
    """Get all candidates for the search interface"""
    try:
        candidates = load_candidates()
        return jsonify({
            'success': True,
            'candidates': candidates,
            'total': len(candidates)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_questions', methods=['POST'])
def generate_questions():
    """Generate screening questions for a candidate"""
    try:
        data = request.get_json()
        job_description = data.get('job_description', '')
        candidate_id = data.get('candidate_id', '')
        
        if not job_description.strip():
            return jsonify({'error': 'Job description is required'}), 400
        
        # Find the candidate
        candidates = load_candidates()
        candidate = next((c for c in candidates if c.get('id') == candidate_id), None)
        
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Generate questions using AI matcher
        questions = ai_matcher.generate_screening_questions(job_description, candidate)
        
        return jsonify({
            'success': True,
            'questions': questions,
            'ai_enabled': ai_matcher.ai_available
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_analytics')
def get_analytics():
    try:
        candidates = load_candidates()
        analytics = generate_analytics(candidates)
        
        return jsonify({
            'success': True,
            'analytics': analytics
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 🆕 UPDATED: Health check endpoint with PeopleGPT status
@app.route('/api/health')
def health_check():
    """Health check endpoint with PeopleGPT status"""
    return jsonify({
        'status': 'healthy',
        'app': 'HireAI',
        'component': 'PeopleGPT',
        'ai_enabled': ai_matcher.ai_available if ai_matcher else False,
        'gemini_available': ai_matcher.ai_available if ai_matcher else False,
        'peoplegpt_enabled': query_parser is not None,
        'total_candidates': len(load_candidates()),
        'user': 'pranamya-jain',
        'team': 'Seeds! 🌱',
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ' UTC'
    })

@app.route('/api/export_candidates', methods=['POST'])
def export_candidates():
    """Export search results to CSV"""
    try:
        data = request.get_json()
        candidates = data.get('candidates', [])
        format_type = data.get('format', 'csv')  # csv, json, pdf
        
        if format_type == 'csv':
            return export_to_csv(candidates)
        elif format_type == 'json':
            return export_to_json(candidates)
        else:
            return jsonify({'error': 'Unsupported format'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def save_candidate(parsed_data, filename):
    """Save candidate to our simple JSON database"""
    candidate_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    candidate = {
        'id': candidate_id,
        'filename': filename,
        'uploaded_at': datetime.now().isoformat(),
        **parsed_data
    }
    
    # Load existing candidates
    candidates_file = 'data/candidates.json'
    candidates = []
    
    if os.path.exists(candidates_file):
        with open(candidates_file, 'r') as f:
            try:
                candidates = json.load(f)
            except json.JSONDecodeError:
                candidates = []
    
    candidates.append(candidate)
    
    # Save back to file
    os.makedirs('data', exist_ok=True)
    with open(candidates_file, 'w') as f:
        json.dump(candidates, f, indent=2)
    
    return candidate_id

def load_candidates():
    """Load candidates from our JSON database"""
    candidates_file = 'data/candidates.json'
    
    if os.path.exists(candidates_file):
        try:
            with open(candidates_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    
    return []

def generate_analytics(candidates):
    """Generate analytics from candidate data"""
    if not candidates:
        return {
            'total_candidates': 0,
            'skills_distribution': {},
            'experience_distribution': {},
            'location_distribution': {}
        }
    
    skills_count = {}
    experience_ranges = {'0-2': 0, '3-5': 0, '6-10': 0, '10+': 0}
    locations = {}
    
    for candidate in candidates:
        # Count skills
        for skill in candidate.get('skills', []):
            skills_count[skill] = skills_count.get(skill, 0) + 1
        
        # Experience distribution
        exp = candidate.get('experience_years', 0)
        if exp <= 2:
            experience_ranges['0-2'] += 1
        elif exp <= 5:
            experience_ranges['3-5'] += 1
        elif exp <= 10:
            experience_ranges['6-10'] += 1
        else:
            experience_ranges['10+'] += 1
        
        # Location distribution
        location = candidate.get('location', 'Unknown')
        locations[location] = locations.get(location, 0) + 1
    
    return {
        'total_candidates': len(candidates),
        'skills_distribution': dict(sorted(skills_count.items(), key=lambda x: x[1], reverse=True)[:10]),
        'experience_distribution': experience_ranges,
        'location_distribution': locations
    }

def export_to_csv(candidates):
    """Export candidates to CSV format"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    headers = ['Name', 'Email', 'Experience (Years)', 'Location', 'Skills', 'Match Score', 'Match Reasons', 'Overall Fit']
    writer.writerow(headers)
    
    # Write candidate data
    for candidate in candidates:
        row = [
            candidate.get('name', 'N/A'),
            candidate.get('email', 'N/A'),
            candidate.get('experience_years', 0),
            candidate.get('location', 'N/A'),
            ', '.join(candidate.get('skills', [])),
            f"{candidate.get('match_score', 0)}%",
            '; '.join(candidate.get('match_reasons', [])),
            candidate.get('overall_fit', 'N/A')
        ]
        writer.writerow(row)
    
    # Create response
    output.seek(0)
    
    # Create a bytes buffer
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'candidates_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

def export_to_json(candidates):
    """Export candidates to JSON format"""
    export_data = {
        'export_date': datetime.now().isoformat(),
        'total_candidates': len(candidates),
        'candidates': candidates
    }
    
    mem = io.BytesIO()
    mem.write(json.dumps(export_data, indent=2).encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='application/json',
        as_attachment=True,
        download_name=f'candidates_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

def generate_export_insights(analytics):
    """Generate insights for export"""
    insights = []
    
    # Top skills insight
    skills = list(analytics['skills_distribution'].items())
    if skills:
        top_skill = skills[0]
        insights.append(f"Most in-demand skill: {top_skill[0]} ({top_skill[1]} candidates)")
    
    # Experience distribution insight
    exp_data = analytics['experience_distribution']
    senior_count = exp_data.get('6-10', 0) + exp_data.get('10+', 0)
    total = sum(exp_data.values())
    if total > 0:
        senior_percentage = (senior_count / total) * 100
        insights.append(f"Senior talent percentage: {senior_percentage:.1f}%")
    
    return insights

# Add these imports to your app.py
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    import pandas as pd
    ADVANCED_EXPORT_AVAILABLE = True
    print("✅ Advanced export libraries (reportlab, pandas) available")
except ImportError:
    ADVANCED_EXPORT_AVAILABLE = False
    print("⚠️ Advanced export libraries not available. Install with: pip install reportlab pandas openpyxl")

@app.route('/api/export_analytics', methods=['POST'])
def export_analytics():
    """Export analytics dashboard in multiple formats"""
    try:
        data = request.get_json()
        format_type = data.get('format', 'json')  # json, csv, pdf, excel
        
        candidates = load_candidates()
        analytics = generate_analytics(candidates)
        
        if format_type == 'json':
            return export_analytics_json(analytics)
        elif format_type == 'csv':
            return export_analytics_csv(analytics)
        elif format_type == 'pdf' and ADVANCED_EXPORT_AVAILABLE:
            return export_analytics_pdf(analytics)
        elif format_type == 'excel' and ADVANCED_EXPORT_AVAILABLE:
            return export_analytics_excel(analytics)
        else:
            return jsonify({'error': 'Unsupported format or missing dependencies. Install: pip install reportlab pandas openpyxl'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def export_analytics_json(analytics):
    """Export analytics as JSON"""
    export_data = {
        'generated_at': datetime.now().isoformat(),
        'generated_by': 'pranamya-jain',
        'report_type': 'HireAI Analytics Dashboard',
        'total_candidates': len(load_candidates()),
        'analytics': analytics,
        'insights': generate_export_insights(analytics),
        'ai_enabled': ai_matcher.ai_available if ai_matcher else False,
        'peoplegpt_enabled': query_parser is not None
    }
    
    mem = io.BytesIO()
    mem.write(json.dumps(export_data, indent=2).encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='application/json',
        as_attachment=True,
        download_name=f'analytics_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

def export_analytics_csv(analytics):
    """Export analytics as CSV (multiple sheets in one file)"""
    output = io.StringIO()
    
    # Write header
    output.write("HireAI Analytics Report\n")
    output.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    output.write(f"Generated by: pranamya-jain\n\n")
    
    # Summary metrics
    output.write("SUMMARY METRICS\n")
    output.write("Metric,Value\n")
    output.write(f"Total Candidates,{analytics['total_candidates']}\n")
    
    exp_data = analytics['experience_distribution']
    senior_count = exp_data.get('6-10', 0) + exp_data.get('10+', 0)
    total = sum(exp_data.values()) if exp_data.values() else 1
    senior_percentage = (senior_count / total) * 100
    output.write(f"Senior Talent Percentage,{senior_percentage:.1f}%\n")
    
    skills = list(analytics['skills_distribution'].items())
    if skills:
        top_skill = skills[0]
        output.write(f"Most Common Skill,{top_skill[0]} ({top_skill[1]} candidates)\n")
    
    output.write("\n")
    
    # Skills distribution
    output.write("SKILLS DISTRIBUTION\n")
    output.write("Skill,Count,Percentage\n")
    total_skills = sum(analytics['skills_distribution'].values()) if analytics['skills_distribution'] else 1
    for skill, count in analytics['skills_distribution'].items():
        percentage = (count / total_skills) * 100
        output.write(f"{skill},{count},{percentage:.1f}%\n")
    
    output.write("\n")
    
    # Experience distribution
    output.write("EXPERIENCE DISTRIBUTION\n")
    output.write("Experience Range,Count,Percentage\n")
    total_exp = sum(analytics['experience_distribution'].values()) if analytics['experience_distribution'] else 1
    for exp_range, count in analytics['experience_distribution'].items():
        percentage = (count / total_exp) * 100
        output.write(f"{exp_range} years,{count},{percentage:.1f}%\n")
    
    output.write("\n")
    
    # Location distribution
    output.write("LOCATION DISTRIBUTION\n")
    output.write("Location,Count,Percentage\n")
    total_locations = sum(analytics['location_distribution'].values()) if analytics['location_distribution'] else 1
    for location, count in analytics['location_distribution'].items():
        percentage = (count / total_locations) * 100
        output.write(f"{location},{count},{percentage:.1f}%\n")
    
    # AI Insights
    output.write("\n")
    output.write("AI INSIGHTS\n")
    insights = generate_export_insights(analytics)
    for i, insight in enumerate(insights, 1):
        output.write(f"Insight {i},{insight}\n")
    
    # Create response
    output.seek(0)
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'analytics_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

def export_analytics_excel(analytics):
    """Export analytics as Excel with multiple sheets"""
    if not ADVANCED_EXPORT_AVAILABLE:
        return jsonify({'error': 'Excel export requires pandas and openpyxl. Install with: pip install pandas openpyxl'}), 500
        
    try:
        # Create Excel file in memory
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['Total Candidates', 'Report Generated', 'Generated By'],
                'Value': [
                    analytics['total_candidates'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'pranamya-jain'
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            # Skills distribution sheet
            if analytics['skills_distribution']:
                skills_data = pd.DataFrame(list(analytics['skills_distribution'].items()), 
                                         columns=['Skill', 'Count'])
                total_skills = skills_data['Count'].sum()
                skills_data['Percentage'] = (skills_data['Count'] / total_skills * 100).round(1)
                skills_data.to_excel(writer, sheet_name='Skills Distribution', index=False)
            
            # Experience distribution sheet
            if analytics['experience_distribution']:
                exp_data = pd.DataFrame(list(analytics['experience_distribution'].items()), 
                                      columns=['Experience Range', 'Count'])
                total_exp = exp_data['Count'].sum()
                exp_data['Percentage'] = (exp_data['Count'] / total_exp * 100).round(1)
                exp_data.to_excel(writer, sheet_name='Experience Distribution', index=False)
            
            # Location distribution sheet
            if analytics['location_distribution']:
                loc_data = pd.DataFrame(list(analytics['location_distribution'].items()), 
                                      columns=['Location', 'Count'])
                total_loc = loc_data['Count'].sum()
                loc_data['Percentage'] = (loc_data['Count'] / total_loc * 100).round(1)
                loc_data.to_excel(writer, sheet_name='Location Distribution', index=False)
            
            # Insights sheet
            insights = generate_export_insights(analytics)
            if insights:
                insights_data = pd.DataFrame({
                    'Insight Number': range(1, len(insights) + 1),
                    'AI Insight': insights
                })
                insights_data.to_excel(writer, sheet_name='AI Insights', index=False)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'analytics_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
    except Exception as e:
        return jsonify({'error': f'Excel export failed: {str(e)}'}), 500

def export_analytics_pdf(analytics):
    """Export analytics as PDF report"""
    if not ADVANCED_EXPORT_AVAILABLE:
        return jsonify({'error': 'PDF export requires reportlab. Install with: pip install reportlab'}), 500
        
    try:
        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#667eea')
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#333333')
        )
        
        story = []
        
        # Title and header
        story.append(Paragraph("HireAI Analytics Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC", styles['Normal']))
        story.append(Paragraph(f"Generated by: pranamya-jain", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary metrics
        story.append(Paragraph("Summary Metrics", heading_style))
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Candidates', str(analytics['total_candidates'])]
        ]
        
        # Calculate additional metrics
        if analytics['skills_distribution']:
            top_skill = list(analytics['skills_distribution'].items())[0]
            summary_data.append(['Most Common Skill', f"{top_skill[0]} ({top_skill[1]} candidates)"])
        
        if analytics['experience_distribution']:
            exp_data = analytics['experience_distribution']
            senior_count = exp_data.get('6-10', 0) + exp_data.get('10+', 0)
            total = sum(exp_data.values())
            if total > 0:
                senior_percentage = (senior_count / total) * 100
                summary_data.append(['Senior Talent %', f"{senior_percentage:.1f}%"])
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Skills distribution
        if analytics['skills_distribution']:
            story.append(Paragraph("Top Skills Distribution", heading_style))
            
            skills_data = [['Skill', 'Count', 'Percentage']]
            total_skills = sum(analytics['skills_distribution'].values())
            
            for skill, count in list(analytics['skills_distribution'].items())[:10]:  # Top 10
                percentage = (count / total_skills * 100)
                skills_data.append([skill, str(count), f"{percentage:.1f}%"])
            
            skills_table = Table(skills_data)
            skills_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#36A2EB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(skills_table)
            story.append(Spacer(1, 20))
        
        # AI Insights
        insights = generate_export_insights(analytics)
        if insights:
            story.append(Paragraph("AI-Powered Insights", heading_style))
            for i, insight in enumerate(insights, 1):
                story.append(Paragraph(f"{i}. {insight}", styles['Normal']))
                story.append(Spacer(1, 6))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'analytics_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': f'PDF export failed: {str(e)}'}), 500

# Helper function to integrate PeopleGPT with existing search
def search_candidates_internal(search_request):
    """
    Internal function to reuse existing search logic for PeopleGPT
    """
    try:
        job_description = search_request.get('job_description', '')
        filters = search_request.get('filters', {})
        
        # Load candidates from our database
        candidates = load_candidates()
        
        if not candidates:
            return []
        
        # Use AI to match candidates
        matched_candidates = ai_matcher.match_candidates(
            job_description, 
            candidates, 
            filters
        )
        
        return matched_candidates
        
    except Exception as e:
        print(f"❌ Error in search_candidates_internal: {e}")
        return []

if __name__ == '__main__':
    print("🚀 Starting HireAI Application with PeopleGPT...")
    print(f"👤 User: pranamya-jain")
    print(f"🌱 Team: Seeds!")
    print(f"🕐 Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"🤖 AI enabled: {ai_matcher.ai_available if ai_matcher else False}")
    print(f"🗨️ PeopleGPT enabled: {query_parser is not None}")
    print(f"📊 Advanced exports: {ADVANCED_EXPORT_AVAILABLE}")
    print(f"🔗 PeopleGPT available at: http://localhost:5001/search")
    print("-" * 60)
    app.run(debug=True, port=5001)