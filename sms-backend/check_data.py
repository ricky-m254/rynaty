import os
import django

# 1. Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django_tenants.utils import schema_context
from school.models import Student, FeeStructure, Term

# 2. Check Data in Tenant Schema
schema_name = 'demo_school'

with schema_context(schema_name):
    print(f"--- Checking Data for Schema: '{schema_name}' ---")
    
    student_count = Student.objects.count()
    print(f"Students: {student_count}")
    
    fee_count = FeeStructure.objects.count()
    print(f"Fee Structures: {fee_count}")
    
    term_count = Term.objects.count()
    print(f"Terms: {term_count}")
    
    print(f"--- Status: {'DATA EXISTS (Dropdowns should work)' if (student_count > 0) else 'NO DATA (Dropdowns are Grey)'} ---")