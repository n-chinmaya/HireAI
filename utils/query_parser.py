import re
import json
from typing import Dict, List, Optional, Union
from datetime import datetime

class NaturalLanguageQueryParser:
    """
    PeopleGPT - Natural Language Query Parser for HireAI
    Built by Team Seeds! 🌱
    
    Converts natural language queries into structured search parameters
    Example: "Find senior ML engineers with Python in SF, remote OK"
    """
    
    def __init__(self):
        self.user = "pranamya-jain"  # Current user context
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Experience level mappings
        self.experience_levels = {
            'intern': {'min': 0, 'max': 1, 'keywords': ['intern', 'internship', 'entry', 'graduate', 'junior']},
            'junior': {'min': 0, 'max': 2, 'keywords': ['junior', 'entry', 'entry-level', 'new grad', 'fresh']},
            'mid': {'min': 2, 'max': 5, 'keywords': ['mid', 'middle', 'intermediate', 'mid-level']},
            'senior': {'min': 5, 'max': 10, 'keywords': ['senior', 'sr', 'lead', 'experienced', 'expert']},
            'principal': {'min': 8, 'max': 15, 'keywords': ['principal', 'staff', 'architect', 'director', 'head']},
            'executive': {'min': 10, 'max': 20, 'keywords': ['vp', 'cto', 'ceo', 'executive', 'c-level']}
        }
        
        # Skills expansion mapping
        self.skills_mapping = {
            'ml': ['Machine Learning', 'ML', 'TensorFlow', 'PyTorch', 'Scikit-learn'],
            'ai': ['Artificial Intelligence', 'AI', 'Machine Learning', 'Deep Learning'],
            'python': ['Python', 'Django', 'Flask', 'FastAPI', 'Pandas', 'NumPy'],
            'js': ['JavaScript', 'JS', 'Node.js', 'React', 'Vue', 'Angular'],
            'react': ['React', 'React.js', 'ReactJS', 'Next.js', 'Redux'],
            'node': ['Node.js', 'NodeJS', 'Express.js', 'Nest.js'],
            'java': ['Java', 'Spring', 'Spring Boot', 'Hibernate'],
            'dotnet': ['.NET', 'C#', 'ASP.NET', 'Entity Framework'],
            'devops': ['DevOps', 'Docker', 'Kubernetes', 'AWS', 'Azure', 'GCP'],
            'cloud': ['AWS', 'Azure', 'GCP', 'Cloud', 'Kubernetes', 'Docker'],
            'sql': ['SQL', 'MySQL', 'PostgreSQL', 'Oracle', 'Database'],
            'nosql': ['MongoDB', 'Redis', 'Cassandra', 'DynamoDB', 'NoSQL'],
            'frontend': ['Frontend', 'React', 'Vue', 'Angular', 'HTML', 'CSS', 'JavaScript'],
            'backend': ['Backend', 'Node.js', 'Python', 'Java', 'API', 'Microservices'],
            'fullstack': ['Full Stack', 'Fullstack', 'Frontend', 'Backend', 'MEAN', 'MERN']
        }
        
        # Location normalization
        self.location_mapping = {
            'sf': ['San Francisco', 'SF', 'Bay Area'],
            'nyc': ['New York', 'NYC', 'New York City', 'Manhattan'],
            'la': ['Los Angeles', 'LA', 'California'],
            'seattle': ['Seattle', 'Washington'],
            'boston': ['Boston', 'Massachusetts'],
            'austin': ['Austin', 'Texas'],
            'denver': ['Denver', 'Colorado'],
            'chicago': ['Chicago', 'Illinois'],
            'atlanta': ['Atlanta', 'Georgia'],
            'remote': ['Remote', 'Work from home', 'WFH', 'Distributed']
        }
        
        # Remote work indicators
        self.remote_keywords = ['remote', 'wfh', 'work from home', 'distributed', 'anywhere', 'home']
        
        # Negative keywords (to exclude)
        self.negative_keywords = ['not', 'without', 'except', 'exclude', 'no']

    def parse_query(self, query: str) -> Dict:
        """
        Main parsing method - converts natural language to structured search
        
        Args:
            query (str): Natural language search query
            
        Returns:
            Dict: Structured search parameters
        """
        query_lower = query.lower().strip()
        
        # Log the parsing attempt
        print(f"[PeopleGPT] Parsing query by {self.user}: '{query}'")
        
        parsed_result = {
            'original_query': query,
            'parsed_by': self.user,
            'parsed_at': self.timestamp,
            'job_description': '',  # Will be built from components
            'filters': {
                'min_experience': None,
                'required_skills': [],
                'location': '',
                'remote_ok': False
            },
            'extracted_components': {
                'experience_level': None,
                'skills': [],
                'locations': [],
                'work_arrangement': None,
                'role_type': None
            },
            'confidence_score': 0.0,
            'suggestions': []
        }
        
        # Extract components
        self._extract_experience_level(query_lower, parsed_result)
        self._extract_skills(query_lower, parsed_result)
        self._extract_locations(query_lower, parsed_result)
        self._extract_work_arrangement(query_lower, parsed_result)
        self._extract_role_type(query_lower, parsed_result)
        
        # Build job description from components
        self._build_job_description(parsed_result)
        
        # Calculate confidence score
        self._calculate_confidence(parsed_result)
        
        # Generate suggestions
        self._generate_suggestions(parsed_result)
        
        return parsed_result

    def _extract_experience_level(self, query: str, result: Dict):
        """Extract experience level and convert to years"""
        for level, config in self.experience_levels.items():
            for keyword in config['keywords']:
                if keyword in query:
                    result['extracted_components']['experience_level'] = level
                    result['filters']['min_experience'] = config['min']
                    break
            if result['extracted_components']['experience_level']:
                break
        
        # Look for explicit year mentions
        year_matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', query)
        if year_matches:
            years = int(year_matches[0])
            result['filters']['min_experience'] = years
            if years >= 8:
                result['extracted_components']['experience_level'] = 'principal'
            elif years >= 5:
                result['extracted_components']['experience_level'] = 'senior'
            elif years >= 2:
                result['extracted_components']['experience_level'] = 'mid'
            else:
                result['extracted_components']['experience_level'] = 'junior'

    def _extract_skills(self, query: str, result: Dict):
        """Extract and expand skills from query"""
        extracted_skills = set()
        
        # Direct skill mapping
        for skill_key, skill_variants in self.skills_mapping.items():
            for variant in skill_variants:
                if variant.lower() in query:
                    extracted_skills.update(skill_variants)
                    break
        
        # Common technology patterns
        tech_patterns = [
            r'\b(python|java|javascript|typescript|go|rust|php|ruby|swift|kotlin)\b',
            r'\b(react|vue|angular|django|flask|spring|express|laravel)\b',
            r'\b(aws|azure|gcp|docker|kubernetes|jenkins|git)\b',
            r'\b(mysql|postgresql|mongodb|redis|elasticsearch)\b'
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                skill_name = match.title()
                extracted_skills.add(skill_name)
                # Add related skills
                if match.lower() in self.skills_mapping:
                    extracted_skills.update(self.skills_mapping[match.lower()])
        
        result['extracted_components']['skills'] = list(extracted_skills)
        result['filters']['required_skills'] = list(extracted_skills)

    def _extract_locations(self, query: str, result: Dict):
        """Extract location preferences"""
        locations = []
        
        # Check location mapping
        for loc_key, loc_variants in self.location_mapping.items():
            for variant in loc_variants:
                if variant.lower() in query:
                    locations.extend(loc_variants)
                    break
        
        # Look for city, state patterns
        city_state_pattern = r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)'
        matches = re.findall(city_state_pattern, query)
        locations.extend(matches)
        
        result['extracted_components']['locations'] = list(set(locations))
        if locations:
            result['filters']['location'] = locations[0]  # Use first location for primary filter

    def _extract_work_arrangement(self, query: str, result: Dict):
        """Extract remote/hybrid/onsite preferences"""
        if any(keyword in query for keyword in self.remote_keywords):
            result['extracted_components']['work_arrangement'] = 'remote'
            result['filters']['remote_ok'] = True
        elif 'hybrid' in query:
            result['extracted_components']['work_arrangement'] = 'hybrid'
        elif 'onsite' in query or 'on-site' in query or 'office' in query:
            result['extracted_components']['work_arrangement'] = 'onsite'

    def _extract_role_type(self, query: str, result: Dict):
        """Extract role/position type"""
        role_patterns = {
            'engineer': ['engineer', 'developer', 'programmer', 'coder'],
            'manager': ['manager', 'lead', 'head', 'director'],
            'designer': ['designer', 'ux', 'ui', 'graphic'],
            'analyst': ['analyst', 'data scientist', 'researcher'],
            'consultant': ['consultant', 'advisor', 'specialist']
        }
        
        for role_type, keywords in role_patterns.items():
            if any(keyword in query for keyword in keywords):
                result['extracted_components']['role_type'] = role_type
                break

    def _build_job_description(self, result: Dict):
        """Build a coherent job description from extracted components"""
        components = result['extracted_components']
        description_parts = []
        
        # Add role and experience
        if components['role_type'] and components['experience_level']:
            description_parts.append(f"Looking for a {components['experience_level']} {components['role_type']}")
        elif components['role_type']:
            description_parts.append(f"Looking for a {components['role_type']}")
        elif components['experience_level']:
            description_parts.append(f"Looking for a {components['experience_level']} professional")
        
        # Add skills
        if components['skills']:
            skills_str = ', '.join(components['skills'][:5])  # Limit to top 5
            description_parts.append(f"with expertise in {skills_str}")
        
        # Add location
        if components['locations']:
            if result['filters']['remote_ok']:
                description_parts.append(f"located in {components['locations'][0]} or remote")
            else:
                description_parts.append(f"located in {components['locations'][0]}")
        elif result['filters']['remote_ok']:
            description_parts.append("open to remote work")
        
        # Add experience requirement
        if result['filters']['min_experience']:
            description_parts.append(f"Minimum {result['filters']['min_experience']} years of experience required")
        
        result['job_description'] = '. '.join(description_parts) + '.'

    def _calculate_confidence(self, result: Dict):
        """Calculate confidence score for the parsing"""
        score = 0.0
        components = result['extracted_components']
        
        # Points for each extracted component
        if components['experience_level']: score += 0.2
        if components['skills']: score += 0.3
        if components['locations']: score += 0.2
        if components['work_arrangement']: score += 0.15
        if components['role_type']: score += 0.15
        
        # Bonus for having job description
        if result['job_description']: score += 0.1
        
        result['confidence_score'] = min(1.0, score)

    def _generate_suggestions(self, result: Dict):
        """Generate query improvement suggestions"""
        suggestions = []
        components = result['extracted_components']
        
        if not components['experience_level']:
            suggestions.append("Consider specifying experience level (e.g., 'senior', '3+ years')")
        
        if not components['skills']:
            suggestions.append("Add specific skills or technologies (e.g., 'Python', 'React')")
        
        if not components['locations'] and not result['filters']['remote_ok']:
            suggestions.append("Specify location preference or mention 'remote OK'")
        
        if result['confidence_score'] < 0.5:
            suggestions.append("Try a more specific query for better results")
        
        result['suggestions'] = suggestions

    def get_query_examples(self) -> List[str]:
        """Return example queries for user guidance"""
        return [
            "Find senior Python developers in San Francisco",
            "Show me React engineers with 3+ years experience, remote OK",
            "Looking for ML engineers in NYC or remote",
            "Junior Java developers in Seattle",
            "Senior full-stack engineers with Node.js and React",
            "Data scientists with Python and SQL, any location",
            "DevOps engineers with AWS experience, remote preferred",
            "Frontend developers with Vue.js in Los Angeles"
        ]

    def validate_query(self, query: str) -> Dict:
        """Validate query and provide feedback"""
        if len(query.strip()) < 3:
            return {'valid': False, 'error': 'Query too short'}
        
        if len(query.strip()) > 500:
            return {'valid': False, 'error': 'Query too long (max 500 characters)'}
        
        # Check for meaningful content
        meaningful_words = ['find', 'show', 'looking', 'search', 'get', 'need', 'want']
        has_meaningful_word = any(word in query.lower() for word in meaningful_words)
        has_tech_terms = any(skill in query.lower() for skill in self.skills_mapping.keys())
        
        if not has_meaningful_word and not has_tech_terms:
            return {'valid': False, 'error': 'Query should describe what you\'re looking for'}
        
        return {'valid': True}


# Usage example and testing
if __name__ == "__main__":
    parser = NaturalLanguageQueryParser()
    
    # Test queries
    test_queries = [
        "Find senior ML engineers with Python in SF, remote OK",
        "Show me React developers with 3+ years experience",
        "Looking for junior Java programmers in Seattle",
        "Need DevOps engineers with AWS, any location",
        "Senior full-stack developers with Node.js and React"
    ]
    
    print("🔍 PeopleGPT Query Parser - Test Results")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        result = parser.parse_query(query)
        print(f"✅ Confidence: {result['confidence_score']:.1%}")
        print(f"🎯 Job Description: {result['job_description']}")
        print(f"⚙️  Filters: {result['filters']}")
        if result['suggestions']:
            print(f"💡 Suggestions: {', '.join(result['suggestions'])}")
        print("-" * 30)