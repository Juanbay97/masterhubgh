# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
token_manager — Creación, validación y consumo de tokens de agendamiento.

Los tokens son secrets.token_hex(16) (32 caracteres hex), almacenados en texto
plano en Cita Examen Medico junto con token_expira (Datetime) y token_usado (Check).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta


def create_token(cita_name: str, expiry_days: int = 14) -> str:
	"""
	Genera secrets.token_hex(16), guarda token y token_expira en la Cita.

	Args:
		cita_name: Nombre del documento Cita Examen Medico.
		expiry_days: Días de validez del token (default 14).

	Returns:
		El token generado (string hex de 32 caracteres).
	"""
	import frappe

	token = secrets.token_hex(16)
	expiry = datetime.now() + timedelta(days=expiry_days)
	frappe.db.set_value(
		"Cita Examen Medico",
		cita_name,
		{
			"token": token,
			"token_expira": expiry,
			"token_usado": 0,
		},
	)
	return token


def validate_token(token: str) -> dict:
	"""
	Busca la Cita por token. Lanza frappe.ValidationError si no existe,
	expiró o ya fue usado.

	Args:
		token: Token hex de 32 caracteres.

	Returns:
		Documento Cita Examen Medico como dict.

	Raises:
		frappe.ValidationError: Si el token no existe, expiró o fue usado.
	"""
	import frappe

	cita = frappe.db.get_value(
		"Cita Examen Medico",
		{"token": token},
		[
			"name",
			"token",
			"token_expira",
			"token_usado",
			"estado",
			"candidato",
			"ips",
			"fecha_cita",
			"hora_cita",
			"cargo_al_enviar",
		],
		as_dict=True,
	)

	if not cita:
		frappe.throw("Token de agendamiento no válido.", frappe.ValidationError)

	if cita.get("token_usado"):
		frappe.throw("Este link ya fue utilizado.", frappe.ValidationError)

	expiry = cita.get("token_expira")
	if expiry:
		if isinstance(expiry, str):
			expiry = datetime.fromisoformat(expiry)
		if expiry < datetime.now():
			frappe.throw("El link de agendamiento ha expirado.", frappe.ValidationError)

	return cita


def consume_token(cita_name: str) -> None:
	"""
	Marca token_usado=1 en la Cita después de un agendamiento exitoso.

	Args:
		cita_name: Nombre del documento Cita Examen Medico.
	"""
	import frappe

	frappe.db.set_value("Cita Examen Medico", cita_name, "token_usado", 1)
