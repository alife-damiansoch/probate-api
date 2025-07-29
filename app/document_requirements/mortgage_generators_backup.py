# document_requirements/mortgage_generators.py

import os
import tempfile
from datetime import datetime
from docxtpl import DocxTemplate
from io import BytesIO
import logging
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class MortgageChargeGenerator:
    """Generator for filling DOCX template with mortgage data - Django integration"""

    def __init__(self, template_dir="static/documents",
                 template_filename="Precedent_Mortgage_and_Charge_with_Placeholders.docx"):
        self.template_dir = template_dir
        self.template_filename = template_filename
        self.template_path = os.path.join(template_dir, template_filename)

    @classmethod
    def generate_document(cls, requirement):
        """Main method to generate mortgage document - matches your service pattern"""
        try:
            logger.info(f"Starting mortgage document generation for requirement {requirement.id}")

            # Get context data using your existing pattern
            context = cls._get_mortgage_context(requirement)

            # Create generator instance
            generator = cls()

            # Generate the document and return BytesIO for download
            result = generator._generate_bytesio_response(context, requirement.application.id)

            if result:
                logger.info("Mortgage document generated successfully")
                return result
            else:
                logger.error("Failed to generate mortgage document")
                return None

        except Exception as e:
            logger.error(f"Error generating mortgage document: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    @classmethod
    def generate_temp_pdf_response(cls, requirement):
        """Generate temporary PDF and return BytesIO - FIXED VERSION"""
        temp_docx = None
        temp_pdf = None

        try:
            logger.info(f"Starting PDF generation for requirement {requirement.id}")

            # Get context and generate temporary files
            context = cls._get_mortgage_context(requirement)
            generator = cls()
            temp_docx, temp_pdf = generator.generate_temp_files(context, requirement.application.id)

            # Only return PDF - fail if PDF conversion didn't work
            if temp_pdf and os.path.exists(temp_pdf):
                # Read PDF content into BytesIO
                with open(temp_pdf, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()

                result = BytesIO(pdf_content)
                result.seek(0)
                logger.info("PDF generated successfully")
                return result
            else:
                logger.error("PDF conversion failed - no PDF file generated")
                return None

        except Exception as e:
            logger.error(f"Error generating PDF response: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

        finally:
            # Cleanup temporary files with retry logic for Windows
            cls._cleanup_temp_files(temp_docx, temp_pdf)

    def _generate_bytesio_response(self, context, application_id):
        """Generate document and return BytesIO for Django response"""
        try:
            # Check if template exists
            if not os.path.exists(self.template_path):
                logger.error(f"Template not found at: {self.template_path}")
                return None

            # Render the template with context
            doc = DocxTemplate(self.template_path)
            doc.render(context)

            # Save to BytesIO instead of file
            result = BytesIO()
            doc.save(result)
            result.seek(0)

            logger.info(f"Mortgage document rendered successfully with {len(context)} context variables")
            return result

        except Exception as e:
            logger.error(f"Error rendering document template: {str(e)}")
            return None

    def generate_temp_files(self, context, application_id):
        """Generate temporary DOCX and PDF files - FIXED VERSION"""
        try:
            # Check if template exists
            if not os.path.exists(self.template_path):
                logger.error(f"Template not found at: {self.template_path}")
                return None, None

            # Create temporary files
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include microseconds
            base_filename = f"Mortgage_and_Charge_{application_id}_{timestamp}"

            temp_docx = os.path.join(temp_dir, base_filename + ".docx")
            temp_pdf = os.path.join(temp_dir, base_filename + ".pdf")

            # Render the template with the provided context
            doc = DocxTemplate(self.template_path)
            doc.render(context)
            doc.save(temp_docx)

            # Release the document object explicitly
            doc = None

            logger.info(f"Temporary DOCX created: {temp_docx}")

            # Convert to PDF with proper error handling
            pdf_success = self._convert_docx_to_pdf_safe(temp_docx, temp_pdf)

            if pdf_success:
                logger.info(f"Temporary PDF created: {temp_pdf}")
                return temp_docx, temp_pdf
            else:
                logger.error("PDF conversion failed")
                return temp_docx, None

        except Exception as e:
            logger.error(f"Error generating temporary files: {str(e)}")
            return None, None

    def _convert_docx_to_pdf_safe(self, temp_docx, temp_pdf):
        """Convert DOCX to PDF with proper error handling and resource cleanup"""
        try:
            from docx2pdf import convert

            # Method 1: Try with COM initialization (Windows)
            if self._try_com_conversion(temp_docx, temp_pdf):
                return True

            # Method 2: Try without COM (fallback)
            if self._try_simple_conversion(temp_docx, temp_pdf):
                return True

            logger.error("All PDF conversion methods failed")
            return False

        except ImportError:
            logger.error("docx2pdf not available. Install with: pip install docx2pdf")
            return False
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            return False

    def _try_com_conversion(self, temp_docx, temp_pdf):
        """Try conversion with COM initialization"""
        try:
            from docx2pdf import convert
            import pythoncom

            # Initialize COM
            pythoncom.CoInitialize()

            try:
                convert(temp_docx, temp_pdf)

                if os.path.exists(temp_pdf):
                    logger.info("PDF created using docx2pdf with COM")
                    return True
                else:
                    logger.warning("COM conversion completed but no PDF file created")
                    return False

            finally:
                # Always uninitialize COM
                try:
                    pythoncom.CoUninitialize()
                except:
                    pass

        except ImportError:
            logger.debug("pythoncom not available, trying without COM")
            return False
        except Exception as e:
            logger.warning(f"COM conversion failed: {e}")
            return False

    def _try_simple_conversion(self, temp_docx, temp_pdf):
        """Try conversion without COM"""
        try:
            from docx2pdf import convert

            convert(temp_docx, temp_pdf)

            if os.path.exists(temp_pdf):
                logger.info("PDF created using docx2pdf (simple)")
                return True
            else:
                logger.warning("Simple conversion completed but no PDF file created")
                return False

        except Exception as e:
            logger.warning(f"Simple conversion failed: {e}")
            return False

    @classmethod
    def _cleanup_temp_files(cls, temp_docx, temp_pdf):
        """Cleanup temporary files with retry logic for Windows file locking"""
        import time
        import gc

        # Force garbage collection first
        gc.collect()

        files_to_cleanup = []
        if temp_docx:
            files_to_cleanup.append(temp_docx)
        if temp_pdf:
            files_to_cleanup.append(temp_pdf)

        for file_path in files_to_cleanup:
            if not os.path.exists(file_path):
                continue

            # Try to delete with retries (Windows file locking)
            for attempt in range(3):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up temporary file: {os.path.basename(file_path)}")
                    break
                except PermissionError as e:
                    if attempt < 2:  # Not the last attempt
                        logger.debug(f"File locked, retrying in 0.5s: {os.path.basename(file_path)}")
                        time.sleep(0.5)  # Wait and retry
                    else:
                        logger.warning(f"Could not delete file after 3 attempts: {os.path.basename(file_path)} - {e}")
                except Exception as e:
                    logger.warning(f"Error deleting file {os.path.basename(file_path)}: {e}")
                    break

    @classmethod
    def _get_mortgage_context(cls, requirement):
        """Get context data for mortgage template - follows your existing pattern"""
        application = requirement.application

        # Get today's date formatted for legal documents
        today = timezone.now()
        formatted_date = today.strftime('%d %B %Y')
        deed_date = today.strftime('%d %B %Y')  # Can be customized

        # Get company/lender info from settings (same as your other generators)
        company_address = getattr(settings, 'COMPANY_ADDRESS', '123 Main Street, City, Country')
        company_name = getattr(settings, 'COMPANY_NAME', 'ALI Probate Ireland')
        company_email = getattr(settings, 'COMPANY_EMAIL', 'info@aliprobate.ie')

        # Get borrower/chargor info from application
        chargor_info = cls._get_chargor_info(application)

        # Get property information
        property_info = cls._get_property_info(application)

        # Build the context dictionary matching your placeholder names
        context = {
            # Date fields
            "TODAYS_DATE": formatted_date,
            "DEED_DATE": deed_date,
            "FORM52_DATE": deed_date,
            "NOTICE_DATE": formatted_date,

            # Chargor/Borrower information
            "CHARGOR_NAME": chargor_info.get('name', ''),
            "CHARGOR_ADDRESS": chargor_info.get('address', ''),
            "CHARGOR_CONTACT": chargor_info.get('name', ''),
            "CHARGOR_EMAIL": chargor_info.get('email', ''),

            # Lender information
            "LENDER_NAME": company_name,
            "LENDER_ADDRESS": company_address,
            "LENDER_CONTACT": 'Legal Department',
            "LENDER_EMAIL": company_email,
            "LENDER_NOTICE_ADDRESS": company_address,
            "LENDER_NOTICE_CONTACT": 'Legal Dept.',

            # Property information
            "PROPERTY_FOLIO": property_info.get('folio_number', ''),
            "PROPERTY_REGISTER": property_info.get('register', ''),
            "PROPERTY_COUNTY": property_info.get('county', ''),
            "PROPERTY_DESCRIPTION": property_info.get('description', ''),

            # Contract/Legal information
            "COUNTERPARTY_NAME": '',  # Leave blank for manual entry
            "CONTRACT_DESCRIPTION": '',  # Leave blank for manual entry

            # Witness information - always leave blank for manual completion
            "WITNESS_NAME": '',
            "WITNESS_ADDRESS": '',
            "WITNESS_OCCUPATION": '',
            "LENDER_WITNESS_NAME": '',
            "LENDER_WITNESS_ADDRESS": '',
            "LENDER_WITNESS_OCCUPATION": '',
        }

        # Log what we're filling vs leaving blank
        filled_fields = [k for k, v in context.items() if v]
        blank_fields = [k for k, v in context.items() if not v]

        logger.info(f"Filling {len(filled_fields)} fields: {filled_fields}")
        logger.info(f"Leaving {len(blank_fields)} fields blank for manual entry: {blank_fields}")

        return context

    @classmethod
    def _get_chargor_info(cls, application):
        """Extract chargor info from application - adapt to your model"""
        chargor_info = {
            'name': '',
            'address': '',
            'email': ''
        }

        try:
            # Use applicants (same pattern as your other generators)
            if hasattr(application, 'applicants') and application.applicants.exists():
                primary = application.applicants.first()
                chargor_info['name'] = f"{primary.first_name} {primary.last_name}"

                if hasattr(primary, 'address') and primary.address:
                    address = primary.address
                    address_parts = []
                    if address.line1:
                        address_parts.append(address.line1)
                    if address.line2:
                        address_parts.append(address.line2)
                    if address.town_city:
                        address_parts.append(address.town_city)
                    if address.county:
                        address_parts.append(address.county)
                    if address.eircode:
                        address_parts.append(address.eircode)

                    chargor_info['address'] = ', '.join(address_parts)

                if hasattr(primary, 'email') and primary.email:
                    chargor_info['email'] = primary.email

            # Fallback to user info (same pattern as your other generators)
            elif hasattr(application, 'user') and application.user:
                user = application.user
                chargor_info['name'] = user.name or user.get_full_name() or ''
                chargor_info['email'] = user.email or ''

                if hasattr(user, 'address') and user.address:
                    address = user.address
                    address_parts = []
                    if address.line1:
                        address_parts.append(address.line1)
                    if address.line2:
                        address_parts.append(address.line2)
                    if address.town_city:
                        address_parts.append(address.town_city)
                    if address.county:
                        address_parts.append(address.county)
                    if address.eircode:
                        address_parts.append(address.eircode)

                    chargor_info['address'] = ', '.join(address_parts)

        except Exception as e:
            logger.warning(f"Error extracting chargor info: {str(e)}")

        return chargor_info

    @classmethod
    def _get_property_info(cls, application):
        """Extract property info from application - adapt to your model"""
        property_info = {
            'folio_number': '',
            'register': '',
            'county': '',
            'description': ''
        }

        try:
            # Adapt based on your property model structure
            if hasattr(application, 'property') and application.property:
                prop = application.property

                if hasattr(prop, 'folio_number') and prop.folio_number:
                    property_info['folio_number'] = str(prop.folio_number)

                if hasattr(prop, 'register') and prop.register:
                    property_info['register'] = str(prop.register)

                if hasattr(prop, 'county') and prop.county:
                    property_info['county'] = str(prop.county)

                if hasattr(prop, 'address') and prop.address:
                    property_info['description'] = str(prop.address)
                elif hasattr(prop, 'description') and prop.description:
                    property_info['description'] = str(prop.description)

        except Exception as e:
            logger.warning(f"Error extracting property info: {str(e)}")

        return property_info


# Installation requirements helper
def check_requirements():
    """Check if required packages are installed"""
    required_packages = ['docxtpl', 'python-docx', 'docx2pdf']
    missing_packages = []

    for package in required_packages:
        if package == 'python-docx':
            try:
                import docx
            except ImportError:
                missing_packages.append(package)
        elif package == 'docx2pdf':
            try:
                import docx2pdf
            except ImportError:
                missing_packages.append(package)
        else:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

    if missing_packages:
        logger.error(f"Missing required packages: {missing_packages}")
        logger.error("Install with: pip install " + " ".join(missing_packages))
        return False

    logger.info("All required packages are installed")
    return True
