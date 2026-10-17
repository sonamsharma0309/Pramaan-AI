"""FICTIONAL demo patient charts matched to the bundled sample 835 files by patient last name."""
from pathlib import Path

_D = Path(__file__).resolve().parent
SAMPLES = {"main": _D / "sample_835.edi", "synthetic": _D / "sample_835_synthetic.edi"}

DEMO = {
    "rao": {
        "diagnosis": "Lumbar radiculopathy M54.16",
        "ehr": """Anita Rao, 47-year-old female, presents with low back pain radiating to the left leg for 9 weeks. Pain started after lifting at work and she reports numbness in the left lateral calf and foot.
Over the past 9 weeks she has taken naproxen 500 mg twice daily with no significant improvement. She completed 6 weeks of supervised physical therapy (12 sessions) without relief of radicular symptoms. Activity modification and a home exercise program were also tried.
Examination shows a positive straight leg raise on the left at 40 degrees, decreased sensation over the L5 dermatome, and a diminished left ankle reflex. Strength is 4/5 in left extensor hallucis longus.
Pain score is 8/10 on VAS and limits walking to under 100 meters and sitting beyond 20 minutes. No fever, no bowel or bladder dysfunction.
MRI lumbar spine without contrast is medically necessary to evaluate for disc herniation or nerve root compression and to guide surgical referral. Diagnosis: lumbar radiculopathy M54.16.""",
    },
    "nair": {
        "diagnosis": "Suspected heart failure I50.9",
        "ehr": """Meera Nair, 62-year-old female with hypertension, presents with progressive exertional dyspnea over 3 weeks and bilateral ankle edema.
On examination a grade 2/6 systolic murmur is noted at the apex and jugular venous pressure is elevated. BNP was 640 pg/ml. Chest x-ray shows cardiomegaly and small bilateral pleural effusions.
Transthoracic echocardiogram is indicated to evaluate for heart failure and valvular disease, and results will change medical management. Ordering physician is Dr. A. Mehta, NPI on file; interpreting cardiologist signed report is attached.
Diagnosis: suspected heart failure I50.9 with hypertension.""",
    },
    "verma": {
        "diagnosis": "Primary osteoarthritis, right knee M17.11",
        "ehr": """Rahul Verma, 68-year-old male, has right knee osteoarthritis with progressive pain for 3 years. Standing radiographs show Kellgren-Lawrence grade 4 changes with complete loss of medial joint space and osteophytes.
He failed more than 6 months of conservative therapy including meloxicam, 24 sessions of physical therapy, weight loss of 8 kg, and two corticosteroid injections with only temporary relief.
WOMAC pain score is 18/20 and he cannot climb stairs or walk without a cane, which limits his activities of daily living. BMI is 31.
A prior authorization request was submitted to the payer on 2 August 2026 before surgery and a reference number was issued, but the payer did not process it in time.
Total knee arthroplasty is medically necessary and was performed on 12 August 2026. Diagnosis: primary osteoarthritis right knee M17.11.""",
    },
    "khan": {
        "diagnosis": "Rotator cuff tear, subsequent encounter S46.011D",
        "ehr": """Imran Khan, 55-year-old male, is receiving post-operative rehabilitation after rotator cuff repair performed on 15 June 2026. He has completed 22 physical therapy visits.
Measured shoulder flexion improved from 60 degrees to 125 degrees and strength improved from 3/5 to 4/5. DASH functional score improved from 68 to 41.
A plan of care with measurable goals is documented and reviewed every 30 days. Each 15-minute unit of therapeutic exercise is timed and documented; 3 units were billed per visit.
He remains unable to lift objects overhead and has difficulty dressing independently. Continued therapy is medically necessary with a clinical expectation of measurable improvement. Diagnosis: rotator cuff tear S46.011D.""",
    },
    "doe": {
        "diagnosis": "Internal derangement of left knee M23.92",
        "ehr": """Jane Doe, 34-year-old female, has left knee pain and mechanical locking for 10 weeks after a twisting injury while playing sport.
She tried rest, ibuprofen 400 mg three times daily and 4 weeks of physical therapy with no improvement in locking. Examination shows a positive McMurray test and a joint line effusion.
Weight-bearing x-ray shows no fracture or advanced arthritis. MRI of the left knee without contrast is medically necessary to evaluate for a meniscal tear before arthroscopy planning.""",
    },
}
