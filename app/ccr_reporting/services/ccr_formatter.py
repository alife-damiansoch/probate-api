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
        """Return an ID record with the correct number of columns (72)."""

        def d(val): return '' if val is None else str(val)

        dob = ''
        if personal_info.get('date_of_birth'):
            dob = personal_info['date_of_birth'].strftime('%d%m%Y') if hasattr(personal_info['date_of_birth'],
                                                                               'strftime') else str(
                personal_info['date_of_birth'])

        # Create full address string including Eircode
        address_parts = [
            d(personal_info.get('address_line_1', '')),
            d(personal_info.get('address_line_2', '')),
            d(personal_info.get('city', '')),
            d(personal_info.get('county', '')),
            d(personal_info.get('postal_code', '')),  # Include Eircode in full address
            d(personal_info.get('country', 'IRELAND'))
        ]
        full_address = ' '.join([part for part in address_parts if part]).upper()

        # page 31 of the submission manual
        id_line_parts = [
            'ID',  # 1. Record Type - Must be "ID" for Individual records
            personal_info.get('provider_code', ''),  # 2. Provider Code - 8-digit CIP code assigned by CCR
            '',  # 3. Secondary Provider Code - Non-mandatory, only for specific branch reporting
            reference_date.strftime('%d%m%Y'),  # 4. CIS Reference Date - Date when CIS data was last updated (DDMMYYYY)
            personal_info.get('provider_cis_no', '').replace('CIS_', ''),
            # 5. Provider CIS No - Unique identifier for CIS (max 38 chars)
            d(personal_info.get('forename')).upper(),  # 6. Forename - First name (mandatory, max 70 chars)
            d(personal_info.get('surname')).upper(),  # 7. Surname - Last name (mandatory, max 70 chars)
            '',  # 8. Gender - M/F (non-mandatory)
            dob,  # 9. Date of Birth - DDMMYYYY format (mandatory, min age 14)
            '',  # 10. Field Space for potential future use - Reserved field
            '',  # 11. Institutional Sector - EU regulation classification (non-mandatory)
            '',  # 12. Deceased Alert - 0/1 indicator (non-mandatory)
            'MI',  # 13. Address 1: Address Type - MI=Main Address, AI=Additional Address (mandatory)
            full_address,  # 14. Address 1: Full Address - Complete concatenated address including Eircode
            '',  # 15. Address 1: Address Line1 - Empty when using full address
            '',  # 16. Address 1: Address Line2 - Empty when using full address
            '',  # 17. Address 1: City/Town - Empty when using full address
            '',  # 18. Address 1: County - Empty when using full address
            '',  # 19. Address 1: PostalCode - Empty when using full address
            '',  # 20. Address 1: Country - Empty when using full address
            '',  # 21. Address 1: Eircode - Empty when using full address
            '',  # 22. Address 1: Borrower not contactable - 0/1 indicator (non-mandatory)

            # Address 2 fields (23-32) - Second address if applicable
            '',  # 23. Address 2: Address Type
            '',  # 24. Address 2: Full Address
            '',  # 25. Address 2: Address Line1
            '',  # 26. Address 2: Address Line2
            '',  # 27. Address 2: City/Town
            '',  # 28. Address 2: County
            '',  # 29. Address 2: PostalCode
            '',  # 30. Address 2: Country
            '',  # 31. Address 2: Eircode
            '',  # 32. Address 2: Borrower not contactable

            # Identification Codes (33-36) - Up to 2 identification codes
            '1',  # 33. Identification 1: Type - 1=PPSN, 2=Individual Tax (non-ROI), etc.
            d(personal_info.get('ppsn', '')).upper(),  # 34. Identification 1: Number - PPSN or other ID number
            '',  # 35. Identification 2: Type
            '',  # 36. Identification 2: Number

            # Contact Information (37-40) - Up to 2 contact methods
            '',  # 37. Contact 1: Type - 1=Landline, 2=Mobile, etc.
            '',  # 38. Contact 1: Value - Phone number or contact value
            '',  # 39. Contact 2: Type
            '',  # 40. Contact 2: Value

            '',  # 41. Sector of Economic Activity - NACE classification (non-mandatory)

            # Employment Information (42-43)
            '',  # 42. Employment: Employment Status - Employment status code (non-mandatory)
            '',  # 43. Employment: Occupation Category - Occupation code (non-mandatory)

            # Sole Trader Business Data (44-72) - Only required if CIS is a sole trader
            '',  # 44. Sole Trader: TradeName - Business name (mandatory if sole trader)
            '', '', '', '', '', '', '', '', '', '',  # 45-54. Sole Trader Address 1 fields
            '', '', '', '', '', '', '', '',  # 55-62. Sole Trader Address 2 fields
            '', '', '', '',  # 63-66. Sole Trader Identification codes
            '', '', '', ''  # 67-72. Sole Trader Contact information
        ]
        # Pad to 72 columns
        id_line_parts = (id_line_parts + [''] * ID_FIELD_COUNT)[:ID_FIELD_COUNT]
        return '|'.join(id_line_parts)

    def format_ci_line(self, credit_info, reference_date):
        """
        Return a CI record (instalment contract) for a single payment 'bullet' loan, with correct closure logic.
        Uses 75 fields, as per CCR manual (not 58).
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
        credit_status_map = {'Not Applicable': 'A', 'Settlement': 'G'}  # 'G' for Settlement per manual
        phase_code = contract_phase_map.get(credit_info.get('contract_phase'), 'AC')
        status_code = credit_status_map.get(credit_info.get('credit_status'), 'A')
        is_settled = credit_info.get('is_settled', False)

        # Set payment-related fields for closure
        outstanding_payments = '0' if is_settled else str(credit_info.get('outstanding_payments_number', 1))
        outstanding_balance = '' if is_settled else fmt_amount(credit_info.get('outstanding_balance'))
        next_payment_amount = '' if is_settled else fmt_amount(credit_info.get('next_payment_amount'))
        next_payment_date = '' if is_settled else fmt_date(credit_info.get('next_payment_date'))

        # Build the record as a list of 75 fields:
        ci = [''] * 75

        # -- Header and core details
        ci[0] = 'CI'  # 1. Record Type - Must be "CI" for Instalment Contracts
        ci[1] = credit_info.get('provider_code', '')  # 2. Provider Code - 8-digit CIP code assigned by CCR
        ci[2] = ''  # 3. Secondary Provider Code - Non-mandatory, only for specific branch reporting
        ci[3] = reference_date.strftime('%d%m%Y')  # 4. Contract Reference Date - Last calendar day of month (DDMMYYYY)
        ci[4] = d(credit_info.get('provider_cis_no', '')).replace('CIS_',
                                                                  '')  # 5. Provider CIS No - Unique CIS identifier (max 38 chars)
        ci[5] = 'B'  # 6. Role of CIS - B=Borrower, C=Co-Borrower, G=Guarantor
        ci[6] = '1'  # 7. Consumer Flag - 1=Consumer, 0=Non-Consumer
        ci[7] = d(credit_info.get('provider_contract_no',
                                  ''))  # 8. Provider Contract No - Unique contract identifier (max 38 chars)
        ci[8] = '10'  # 9. Product Type - 22=Other Product Type (see domain table)
        ci[9] = phase_code  # 10. Contract Phase - RQ=Requested, AC=Active, CL=Closed, CA=Closed in Advance
        ci[10] = status_code  # 11. Credit Status - A=Not applicable, H=Legal Proceedings, G=Settlement, etc.
        ci[11] = d(credit_info.get('currency', 'EUR'))  # 12. Currency - Must be EUR for file currency
        ci[12] = d(credit_info.get('original_currency', 'EUR'))  # 13. Original Currency - Original contract currency
        ci[13] = fmt_date(credit_info.get('start_date'))  # 14. Start Date - First drawdown date (DDMMYYYY)
        ci[14] = ''  # 15. Contract Request Date - Credit application date (mandatory if phase=RQ)
        ci[15] = fmt_date(credit_info.get('maturity_date'))  # 16. Maturity Date - Planned end date (DDMMYYYY)
        ci[16] = fmt_date(credit_info.get(
            'contract_end_date'))  # 17. Contract End Actual Date - Actual closure date (mandatory if phase=CL/CA)
        ci[17] = ''  # 18. Payment Made Date - Date of last payment in reporting period TODO implement when payment made
        ci[18] = '18'  # 19. Restructure Event - Restructure type code (see domain table)
        ci[19] = ''  # 20. Reorganised Credit Code - 2=Reorganised Credit (Phase 2 feature)
        ci[20] = '4'  # 21. Interest Rate Type - 1=Variable, 3=Fixed <1yr, 4=Fixed 1-5yr, 7=Other
        ci[21] = 'CHECK'  # 22. Interest Rate - Annual rate (N3,2 format: 3 digits, 2 decimals)
        ci[22] = fmt_amount(credit_info.get('financed_amount'))  # 23. Financed Amount - Total credit amount available
        ci[23] = '1'  # 24. Total Number of Planned Payments - Total payments to maturity
        ci[24] = 'I'  # 25. Payment Frequency - L=Bullet, M=Monthly, W=Weekly, etc.
        ci[25] = 'OTH'  # 26. Payment Method - DIR=Direct Debit, CAS=Cash, CHQ=Cheque, etc.
        ci[26] = ''  # 27. Repayment Type - 1=Interest Only, 2=Fixed Amortisation, 4=Bullet, etc.
        ci[27] = ''  # 28. Purpose of Credit Type - 1=Residential RE, 2=Commercial RE, etc.
        ci[28] = ''  # 29. Exposure Class - CRR/CRD IV exposure classification
        ci[29] = ''  # 30. MOF Link Code - Multi Option Facility link code
        ci[30] = ''  # 31. Payment Made - Sum of payments in reporting period
        ci[31] = ''  # 32. First Payment Date - Date of first agreed payment
        ci[32] = next_payment_date  # 33. Next Payment Date - Next payment due date
        ci[33] = next_payment_amount  # 34. Next Payment Amount - Next amount due
        ci[34] = outstanding_payments  # 35. Outstanding Payments Number - Remaining payments including missed
        ci[35] = outstanding_balance  # 36. Outstanding Balance - Total outstanding including past due
        ci[36] = ''  # 37. Number of payments past due - Overdue payments (with 1 month grace)
        ci[37] = ''  # 38. Amount past due - Overdue amount (no grace period for CBI)
        ci[38] = ''  # 39. Days Past Due - Days overdue (no grace period for CBI)

        # Collateral/Guarantee sections (39-74) - 6 occurrences of 6 fields each
        # Collateral/Guarantee 1 (40-45)
        ci[39] = ''  # 40. Collateral Type 1 - Property, Cash, Personal Guarantee, etc.
        ci[40] = ''  # 41. Provider Guarantor CIS No 1 - CIS number of guarantor
        ci[41] = ''  # 42. Guarantee start date 1 - Guarantee validity start
        ci[42] = ''  # 43. Guarantee end date 1 - Guarantee validity end
        ci[43] = ''  # 44. Personal Recourse Type 1 - F=Full, L=Limited, N=None
        ci[44] = ''  # 45. Personal Recourse Value 1 - Value if limited recourse

        # Collateral/Guarantee 2 (46-51)
        ci[45] = ''  # 46. Collateral Type 2
        ci[46] = ''  # 47. Provider Guarantor CIS No 2
        ci[47] = ''  # 48. Guarantee start date 2
        ci[48] = ''  # 49. Guarantee end date 2
        ci[49] = ''  # 50. Personal Recourse Type 2
        ci[50] = ''  # 51. Personal Recourse Value 2

        # Collateral/Guarantee 3 (52-57)
        ci[51] = ''  # 52. Collateral Type 3
        ci[52] = ''  # 53. Provider Guarantor CIS No 3
        ci[53] = ''  # 54. Guarantee start date 3
        ci[54] = ''  # 55. Guarantee end date 3
        ci[55] = ''  # 56. Personal Recourse Type 3
        ci[56] = ''  # 57. Personal Recourse Value 3

        # Collateral/Guarantee 4 (58-63)
        ci[57] = ''  # 58. Collateral Type 4
        ci[58] = ''  # 59. Provider Guarantor CIS No 4
        ci[59] = ''  # 60. Guarantee start date 4
        ci[60] = ''  # 61. Guarantee end date 4
        ci[61] = ''  # 62. Personal Recourse Type 4
        ci[62] = ''  # 63. Personal Recourse Value 4

        # Collateral/Guarantee 5 (64-69)
        ci[63] = ''  # 64. Collateral Type 5
        ci[64] = ''  # 65. Provider Guarantor CIS No 5
        ci[65] = ''  # 66. Guarantee start date 5
        ci[66] = ''  # 67. Guarantee end date 5
        ci[67] = ''  # 68. Personal Recourse Type 5
        ci[68] = ''  # 69. Personal Recourse Value 5

        # Collateral/Guarantee 6 (70-75)
        ci[69] = ''  # 70. Collateral Type 6
        ci[70] = ''  # 71. Provider Guarantor CIS No 6
        ci[71] = ''  # 72. Guarantee start date 6
        ci[72] = ''  # 73. Guarantee end date 6
        ci[73] = ''  # 74. Personal Recourse Type 6
        ci[74] = ''  # 75. Personal Recourse Value 6

        return '|'.join(ci)

    def create_file_header(self, reference_date):
        ccr_provider_code = settings.CCR_PROVIDER_CODE
        """Create file header line."""
        return f"HD|{ccr_provider_code}|{reference_date.strftime('%d%m%Y')}|1.0|0|MONTHLY CCR SUBMISSION"

    def create_file_footer(self, total_records, reference_date):
        ccr_provider_code = settings.CCR_PROVIDER_CODE
        """Create file footer line."""
        return f"FT|{ccr_provider_code}|{reference_date.strftime('%d%m%Y')}|{total_records}"
