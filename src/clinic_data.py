"""Placeholder clinic data used to build the system prompt.

This is a stand-in for the real RAG pipeline (pgvector + documents table,
see docs/spec.md section 4-5). Replace with retrieved chunks once the RAG
phase is implemented.
"""

CLINIC_NAME = "Clinica Dental Sonrie"
CONTACT_PHONE = "+51 987 654 321"

CLINIC_INFO = """\
Nombre: Clinica Dental Sonrie
Direccion: Av. Arequipa 1234, Miraflores, Lima
Horario de atencion: Lunes a sabado, 9:00 a 19:00. Domingo cerrado.
Telefono de contacto / urgencias: +51 987 654 321

Servicios y precios:
- Limpieza dental (profilaxis): S/ 120
- Consulta general / diagnostico: S/ 60
- Resina (por pieza): S/ 150
- Extraccion simple: S/ 100
- Blanqueamiento dental (consultorio): S/ 350
- Ortodoncia (brackets metalicos, evaluacion inicial): S/ 80, tratamiento desde S/ 2500

Notas:
- No se ofrece blanqueamiento con laser.
- No se realizan tratamientos de urgencia fuera del horario de atencion;
  para urgencias fuera de horario, derivar al telefono de contacto.
"""
