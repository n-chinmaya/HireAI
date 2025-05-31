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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

@app.route('/search')
def search_page():
    return render_template('search.html')

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
            'ai_enabled': ai_matcher.ai_available
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'ai_enabled': ai_matcher.ai_available if ai_matcher else False,
        'gemini_available': ai_matcher.ai_available if ai_matcher else False,
        'total_candidates': len(load_candidates())
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
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import pandas as pd

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
        elif format_type == 'pdf':
            return export_analytics_pdf(analytics)
        elif format_type == 'excel':
            return export_analytics_excel(analytics)
        else:
            return jsonify({'error': 'Unsupported format'}), 400
            
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
        'ai_enabled': ai_matcher.ai_available if ai_matcher else False
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
        
    except ImportError:
        return jsonify({'error': 'Excel export requires pandas and openpyxl. Install with: pip install pandas openpyxl'}), 500

def export_analytics_pdf(analytics):
    """Export analytics as PDF report"""
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
        
    except ImportError:
        return jsonify({'error': 'PDF export requires reportlab. Install with: pip install reportlab'}), 500

if __name__ == '__main__':
    print("🚀 Starting HireAI Application...")
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"🤖 AI enabled: {ai_matcher.ai_available if ai_matcher else False}")
    app.run(debug=True, port=5001)