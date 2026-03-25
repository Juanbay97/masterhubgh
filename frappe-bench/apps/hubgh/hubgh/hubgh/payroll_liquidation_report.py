"""
Payroll Liquidation Report - Excel/Print report generation for liquidations.

Sprint 6: Report generation for period-end settlements.
"""

import frappe
from frappe.utils import now_datetime, getdate, format_date
from frappe.utils.xlsxutils import make_xlsx
from typing import Dict, Any, List
import io

from hubgh.hubgh.payroll_employee_compat import get_payroll_employee_context


class PayrollLiquidationReport:
    """Generate liquidation reports in various formats."""
    
    def __init__(self, period: str):
        self.period = period
        self.period_doc = frappe.get_doc("Payroll Period Config", period)
    
    def generate_excel(self, liquidations: List[Dict[str, Any]]) -> bytes:
        """Generate Excel report from liquidation data."""
        data = []
        
        # Headers
        headers = [
            "Documento",
            "Empleado",
            "Vacaciones",
            "Cesantías",
            "Intereses Cesantías",
            "Prima Servicios",
            "Total"
        ]
        data.append(headers)
        
        # Data rows
        for liq in liquidations:
            employee_context = get_payroll_employee_context(liq["employee_id"])
            emp_name = employee_context.get("employee_name") or liq.get("employee_name") or liq["employee_id"]
            document_number = employee_context.get("document_number") or liq["employee_id"]

            row = [
                document_number,
                emp_name,
                liq["vacaciones"]["vacation_pay"],
                liq["cesantias"]["cesantias"],
                liq["intereses_cesantias"]["intereses"],
                liq["prima_servicios"]["prima"],
                liq["total_liquidacion"],
            ]
            data.append(row)
        
        # Totals row
        total_row = [
            "TOTALES",
            f"{len(liquidations)} empleados",
            sum(l["vacaciones"]["vacation_pay"] for l in liquidations),
            sum(l["cesantias"]["cesantias"] for l in liquidations),
            sum(l["intereses_cesantias"]["intereses"] for l in liquidations),
            sum(l["prima_servicios"]["prima"] for l in liquidations),
            sum(l["total_liquidacion"] for l in liquidations)
        ]
        data.append(total_row)
        
        # Create xlsx
        xlsx_file = make_xlsx(data, "Liquidaciones")
        return xlsx_file.getvalue()
    
    def generate_pdf_data(self, liquidations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate data structure for PDF report."""
        totals = {
            "vacaciones": sum(l["vacaciones"]["vacation_pay"] for l in liquidations),
            "cesantias": sum(l["cesantias"]["cesantias"] for l in liquidations),
            "intereses": sum(l["intereses_cesantias"]["intereses"] for l in liquidations),
            "prima": sum(l["prima_servicios"]["prima"] for l in liquidations),
            "total": sum(l["total_liquidacion"] for l in liquidations)
        }
        
        return {
            "doc": self.period_doc,
            "period": self.period,
            "period_start": self.period_doc.start_date,
            "period_end": self.period_doc.end_date,
            "liquidations": liquidations,
            "totals": totals,
            "employee_count": len(liquidations),
            "generated_on": now_datetime(),
            "generated_date": format_date(now_datetime(), "dd MMMM yyyy")
        }


@frappe.whitelist()
def download_liquidation_excel(period: str) -> Any:
    """
    API endpoint to download liquidation Excel report.
    """
    from hubgh.hubgh.payroll_liquidation_service import get_period_liquidations
    
    liquidations = get_period_liquidations(period)
    
    report = PayrollLiquidationReport(period)
    xlsx_data = report.generate_excel(liquidations)
    
    # Return as file download
    frappe.response['filename'] = f'Liquidaciones_{period}_{format_date(now_datetime(), "yyyyMMdd")}.xlsx'
    frappe.response['filecontent'] = xlsx_data
    frappe.response['type'] = 'binary'


@frappe.whitelist()
def get_liquidation_summary(period: str) -> Dict[str, Any]:
    """
    API endpoint to get liquidation summary without details.
    """
    from hubgh.hubgh.payroll_liquidation_service import get_period_liquidations
    
    liquidations = get_period_liquidations(period)
    
    return {
        "period": period,
        "employee_count": len(liquidations),
        "total_vacaciones": sum(l["vacaciones"]["vacation_pay"] for l in liquidations),
        "total_cesantias": sum(l["cesantias"]["cesantias"] for l in liquidations),
        "total_intereses": sum(l["intereses_cesantias"]["intereses"] for l in liquidations),
        "total_prima": sum(l["prima_servicios"]["prima"] for l in liquidations),
        "gran_total": sum(l["total_liquidacion"] for l in liquidations)
    }


@frappe.whitelist()
def get_employee_liquidation_detail(period: str, employee_id: str) -> Dict[str, Any]:
    """
    Get detailed liquidation for a specific employee.
    """
    from hubgh.hubgh.payroll_liquidation_service import PayrollLiquidationService
    
    period_doc = frappe.get_doc("Payroll Period Config", period)
    
    service = PayrollLiquidationService()
    return service.calculate_all_liquidations(
        employee_id,
        period_doc.start_date,
        period_doc.end_date
    )
