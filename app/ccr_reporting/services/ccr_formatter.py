from datetime import datetime
from math import floor

from app import settings

ID_FIELD_COUNT = 58
CI_FIELD_COUNT = 58


class CCRFileFormatter:
    """
    Format data into CCR submission file format with settlement handling
    """

    def format_id_line(self, personal_info, reference_date):
        """Return an ID record with the correct number of columns (58)."""

        def d(val): return '' if val is None else str(val)

        dob = ''
        if personal_info.get('date_of_birth'):
            dob = personal_info['date_of_birth'].strftime('%d%m%Y') if hasattr(personal_info['date_of_birth'],
                                                                               'strftime') else str(
                personal_info['date_of_birth'])

        id_line_parts = [
            'ID',  # 1. Record Type
            personal_info.get('provider_code', ''),  # 2. Provider Code
            '',  # 3. Secondary Provider Code
            reference_date.strftime('%d%m%Y'),  # Contract Reference Date (file date)
            personal_info.get('provider_cis_no', '').replace('CIS_', ''),  # 5. Provider CIS No
            d(personal_info.get('forename')).upper(),
            d(personal_info.get('surname')).upper(),
            '',  # 8. Gender
            dob,  # 9. Date of Birth (DDMMYYYY)
            '',  # 10. Deceased alert
            d(personal_info.get('address_line_1', '')).upper(),  # 11. Address Line 1
            d(personal_info.get('address_line_2', '')).upper(),  # 12. Address Line 2
            d(personal_info.get('city', '')).upper(),  # 13. City
            d(personal_info.get('county', '')).upper(),  # 14. County
            d(personal_info.get('postal_code', '')).upper(),  # 15. Postal Code
            d(personal_info.get('country', 'IRELAND')).upper(),  # 16. Country
            '',  # 17. Eircode
            'PPS',  # 18. Identification Type
            d(personal_info.get('ppsn', '')).upper(),  # 19. Identification Number (PPSN)
            '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
            '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''
        ]
        # Pad to 58 columns
        id_line_parts = (id_line_parts + [''] * ID_FIELD_COUNT)[:ID_FIELD_COUNT]
        return '|'.join(id_line_parts)

    def format_ci_line(self, credit_info, reference_date):
        """
        Return a CI record (instalment contract) for a single payment 'bullet' loan, with correct closure logic.
        Uses 58 fields, as per CCR manual.
        """

        def fmt_amount(float_val):
            try:
                return str(floor(float(float_val)))
            except (TypeError, ValueError):
                return ''

        def d(val):
            return '' if val is None else str(val)

        def fmt_date(val):
            if not val: return ''
            if hasattr(val, 'strftime'):
                return val.strftime('%d%m%Y')
            return str(val)

        # ---- Mapping for phase/status codes (check domain table for your version)
        contract_phase_map = {'Active': 'AC', 'Closed': 'CL', 'Closed In Advance': 'CA'}
        credit_status_map = {'Not Applicable': 'A', 'Settlement': 'S'}
        phase_code = contract_phase_map.get(credit_info.get('contract_phase'), 'AC')
        status_code = credit_status_map.get(credit_info.get('credit_status'), 'A')
        is_settled = credit_info.get('is_settled', False)

        # Set payment-related fields for closure
        outstanding_payments = '0' if is_settled else str(credit_info.get('outstanding_payments_number', 1))
        outstanding_balance = '' if is_settled else fmt_amount(credit_info.get('outstanding_balance'))
        next_payment_amount = '' if is_settled else fmt_amount(credit_info.get('next_payment_amount'))
        next_payment_date = '' if is_settled else fmt_date(credit_info.get('next_payment_date'))

        # Build the record as a list of 58 fields:
        ci = [''] * 58

        # -- Header and core details
        ci[0] = 'CI'  # Record Type
        ci[1] = credit_info.get('provider_code', '')
        ci[2] = ''  # Secondary Provider Code (blank)
        ci[3] = reference_date.strftime('%d%m%Y')  # Contract Reference Date (file date)
        ci[4] = d(credit_info.get('provider_cis_no', '')).replace('CIS_', '')
        ci[5] = 'B'  # Role of CIS
        ci[6] = '1'  # Consumer flag
        ci[7] = d(credit_info.get('provider_contract_no', ''))
        ci[8] = '22'  # Product Type ('22' for "Other" or as per your product)
        ci[9] = phase_code  # Contract Phase
        ci[10] = status_code  # Credit Status
        ci[11] = d(credit_info.get('currency', 'EUR'))
        ci[12] = d(credit_info.get('original_currency', 'EUR'))
        ci[13] = fmt_date(credit_info.get('start_date'))  # Start Date
        ci[14] = ''  # Contract Request Date
        ci[15] = fmt_date(credit_info.get('maturity_date'))  # Maturity Date (expected payout)
        ci[16] = fmt_date(credit_info.get('contract_end_date'))  # Actual End Date (on closure)
        ci[17] = ''  # Payment Made Date
        ci[18] = ''  # Restructure Event
        ci[19] = ''  # Reorganised Credit Code
        ci[20] = '4'  # Interest Rate Type ('4' = Other)
        ci[21] = '0'  # Interest Rate (0 for non-interest/fixed fee)
        ci[22] = fmt_amount(credit_info.get('financed_amount'))  # Financed Amount
        ci[23] = '1'  # Total Number of Planned Payments (1 for bullet)
        ci[24] = 'BU'  # Payment Frequency ("BU" for Bullet)
        ci[25] = ''  # Payment Method
        ci[26] = ''  # First Payment Date
        ci[27] = next_payment_date  # Next Payment Date
        ci[28] = next_payment_amount  # Next Payment Amount
        ci[29] = outstanding_payments  # Outstanding Payments Number
        ci[30] = outstanding_balance  # Outstanding Balance
        # -- The rest: default blanks, unless you have a value
        # You can fill in further indices if your manual specifies!

        return '|'.join(ci)

    def create_file_header(self, reference_date):
        ccr_provider_code = settings.CCR_PROVIDER_CODE
        """Create file header line."""
        return f"HD|{ccr_provider_code}|{reference_date.strftime('%d%m%Y')}|1.0|0|MONTHLY CCR SUBMISSION"

    def create_file_footer(self, total_records, reference_date):
        ccr_provider_code = settings.CCR_PROVIDER_CODE
        """Create file footer line."""
        return f"FT|{ccr_provider_code}|{reference_date.strftime('%d%m%Y')}|{total_records}"
