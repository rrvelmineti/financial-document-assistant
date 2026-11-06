"""A small synthetic financial report PDF for tests. Every name and figure is invented."""
import io
import json

from fpdf import FPDF

PAGES = [
    ["Harbor Point Credit Union", "2025 Annual Report",
     "Message from the Chief Executive",
     "Total assets grew to $412.6 million at December 31, 2025, up from $388.1 million a year earlier.",
     "Membership reached 41,250 members across 9 branches."],
    ["Statement of Financial Condition (in thousands)",
     "Loans to members, net: 301,450",
     "Investments: 74,220",
     "Total assets: 412,600",
     "Member deposits: 362,900",
     "Net worth ratio: 10.4%"],
    ["Statement of Income (in thousands)",
     "Interest income: 21,870",
     "Provision for credit losses: 1,940",
     "Net income: 3,260",
     "The provision increased because delinquent auto loans rose to 1.2% of auto balances."],
]


def report_pdf():
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    for lines in PAGES:
        pdf.add_page()
        for line in lines:
            pdf.multi_cell(0, 7, line)
            pdf.ln(1)
    return bytes(pdf.output())


def fake_gemini(*answers):
    """An opener returning canned Gemini JSON answers in turn, recording the prompts sent."""
    sent, queue = [], list(answers)

    class Response:
        def __init__(self, text):
            self.text = text

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return json.dumps({"candidates": [{"finishReason": "STOP",
                                               "content": {"parts": [{"text": self.text}]}}]}).encode()

    def opener(request, timeout):
        sent.append(json.loads(request.data))
        return Response(json.dumps(queue.pop(0)))
    opener.sent = sent
    return opener


if __name__ == "__main__":
    data = report_pdf()
    print(len(data), "bytes")
    io.BytesIO(data)
