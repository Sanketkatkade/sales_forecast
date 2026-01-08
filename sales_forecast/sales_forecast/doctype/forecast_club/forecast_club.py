# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ForecastClub(Document):
	def validate(self):
		self.validate_items()

	def on_submit(self):
		"""Set initial status on submit"""
		self.db_set("status", "Forecast Planned")

	def before_save(self):
		"""Calculate totals for each item"""
		for item in self.items:
			# Calculate total_batch_qty as sum of all weekly batches
			item.total_batch_qty = (
				(item.w1_batch or 0) +
				(item.w2_batch or 0) +
				(item.w3_batch or 0) +
				(item.w4_batch or 0)
			)

			# Calculate total_qty as total_batch_qty * batch_size
			item.total_qty = item.total_batch_qty * (item.batch_size or 0)

	def validate_items(self):
		"""Validate items before save"""
		from frappe import _

		# Skip validation if no items
		if not self.items:
			return

		for idx, item in enumerate(self.items, start=1):
			# Calculate total_batch_qty
			total_batch = (item.w1_batch or 0) + (item.w2_batch or 0) + (item.w3_batch or 0) + (item.w4_batch or 0)

			# Only validate if at least one weekly batch is set
			if total_batch > 0:
				# Check if batch_size is set when batches are entered
				if not item.batch_size or item.batch_size == 0:
					frappe.throw(_("Row #{0}: Batch Size is required when weekly batches are set for item {1}").format(idx, item.item_code))

	@frappe.whitelist()
	def fetch_material_request_items(self):
		"""Fetch raw materials from BOM based on total_qty for each item"""
		if not self.items:
			frappe.msgprint("No items found. Please fetch forecasts first.")
			return

		# Clear existing material request items
		self.material_request_items = []

		# Dictionary to aggregate raw materials by item_code
		materials_dict = {}

		for item in self.items:
			if not item.bom:
				frappe.msgprint(f"No BOM found for item {item.item_code}")
				continue

			if not item.total_qty:
				continue

			# Get BOM items (raw materials)
			bom_items = frappe.db.get_all(
				"BOM Item",
				filters={"parent": item.bom},
				fields=["item_code", "item_name", "qty", "uom", "stock_uom"]
			)

			for bom_item in bom_items:
				key = bom_item.item_code

				# Calculate required quantity: BOM qty * total_qty
				required_bom_qty = bom_item.qty * item.total_qty

				if key not in materials_dict:
					materials_dict[key] = {
						"item_code": bom_item.item_code,
						"item_name": bom_item.item_name,
						"bom_qty": 0,
						"uom": bom_item.uom or bom_item.stock_uom
					}

				# Aggregate bom_qty
				materials_dict[key]["bom_qty"] += required_bom_qty

		# Add aggregated materials to material_request_items child table
		for material_data in materials_dict.values():
			item_code = material_data["item_code"]

			# Get actual_qty from set_warehouse
			actual_qty = 0
			if self.set_warehouse:
				actual_qty = frappe.db.get_value(
					"Bin",
					{"item_code": item_code, "warehouse": self.set_warehouse},
					"actual_qty"
				) or 0

			# Get company_total_stock (sum of all warehouses in the company)
			company_total_stock = 0
			if self.company:
				company_total_stock = frappe.db.sql("""
					SELECT SUM(b.actual_qty)
					FROM `tabBin` b
					INNER JOIN `tabWarehouse` w ON b.warehouse = w.name
					WHERE b.item_code = %s AND w.company = %s
				""", (item_code, self.company))[0][0] or 0

			self.append("material_request_items", {
				"item_code": material_data["item_code"],
				"item_name": material_data["item_name"],
				"bom_qty": material_data["bom_qty"],
				"uom": material_data["uom"],
				"actual_qty": actual_qty,
				"company_total_stock": company_total_stock
			})

		frappe.msgprint(f"Fetched {len(materials_dict)} raw materials from BOMs")

	@frappe.whitelist()
	def fetch_sales_forecasts(self):
		"""Fetch and aggregate sales forecasts from Forecast Sales Person based on date range"""
		if not self.forecast_start_date or not self.forecast_end_date:
			frappe.msgprint("Please set Forecast Start Date and Forecast End Date")
			return

		if not self.company:
			frappe.msgprint("Please set Company")
			return

		# Clear existing items
		self.items = []

		# Get all submitted Forecast Sales Person documents matching the date range
		forecast_docs = frappe.db.get_all(
			"Forecast Sales Person",
			filters={
				"forecast_start_date": self.forecast_start_date,
				"forecast_end_date": self.forecast_end_date,
				"company": self.company,
				"docstatus": 1
			},
			fields=["name"]
		)

		if not forecast_docs:
			frappe.msgprint("No matching Forecast Sales Person records found for the selected date range and company")
			return

		# Dictionary to aggregate items by item_code
		items_dict = {}

		# Fetch all items from matching forecast documents
		for doc in forecast_docs:
			forecast_items = frappe.db.get_all(
				"Forecast Sales Person Wise Item",
				filters={"parent": doc.name},
				fields=["item_code", "item_name", "week_1", "week_2", "week_3", "week_4"]
			)

			for item in forecast_items:
				key = item.item_code

				if key not in items_dict:
					items_dict[key] = {
						"item_code": item.item_code,
						"item_name": item.item_name,
						"week_1": 0,
						"week_2": 0,
						"week_3": 0,
						"week_4": 0
					}

				# Aggregate weekly quantities
				items_dict[key]["week_1"] += (item.week_1 or 0)
				items_dict[key]["week_2"] += (item.week_2 or 0)
				items_dict[key]["week_3"] += (item.week_3 or 0)
				items_dict[key]["week_4"] += (item.week_4 or 0)

		# Add aggregated items to the items child table
		for item_data in items_dict.values():
			# Get BOM for the item if it exists
			bom = frappe.db.get_value("BOM", {"item": item_data["item_code"], "is_default": 1, "is_active": 1}, "name")

			self.append("items", {
				"item_code": item_data["item_code"],
				"item_name": item_data["item_name"],
				"bom": bom,
				"week_1": item_data["week_1"],
				"week_2": item_data["week_2"],
				"week_3": item_data["week_3"],
				"week_4": item_data["week_4"]
			})

		frappe.msgprint(f"Fetched {len(items_dict)} items from {len(forecast_docs)} sales forecasts")

	@frappe.whitelist()
	def create_material_requests(self):
		"""Create Material Requests from Forecast Club material request items"""
		from frappe import _

		if not self.material_request_items:
			frappe.msgprint("No material request items found. Please fetch material request items first.")
			return

		if self.docstatus != 1:
			frappe.throw(_("Please submit the Forecast Club document before creating Material Requests"))

		# Check if Material Request already exists for this Forecast Club (excluding cancelled)
		existing_mr = frappe.db.sql("""
			SELECT mri.name
			FROM `tabMaterial Request Item` mri
			INNER JOIN `tabMaterial Request` mr ON mri.parent = mr.name
			WHERE mri.custom_forecast_club = %s
			AND mr.docstatus != 2
			LIMIT 1
		""", self.name)

		if existing_mr:
			frappe.throw(_("Material Request already exists for this Forecast Club. Please check existing Material Requests."))

		# Create single Material Request with all items
		mr_items = []
		for item in self.material_request_items:
			# Calculate qty needed (bom_qty - actual_qty)
			qty_needed = item.bom_qty - item.actual_qty

			if qty_needed <= 0:
				continue

			mr_items.append({
				"item_code": item.item_code,
				"qty": qty_needed,
				"schedule_date": self.forecast_end_date,
				"warehouse": self.set_warehouse,
				"custom_forecast_club": self.name
			})

		if not mr_items:
			frappe.msgprint("No items need to be ordered. All items have sufficient stock.")
			return

		# Create Material Request
		mr = frappe.get_doc({
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": self.company,
			"transaction_date": self.date,
			"schedule_date": self.forecast_end_date,
			"items": mr_items
		})

		mr.insert()

		# Update status to Material Requested
		self.db_set("status", "Material Requested")

		frappe.msgprint(f"Created Material Request: {mr.name}")
		return [mr.name]


def on_material_request_cancel(doc, method):
	"""Update Forecast Club status when Material Request is cancelled"""
	# Get all forecast club references from the cancelled Material Request
	forecast_clubs = set()
	for item in doc.items:
		if hasattr(item, 'custom_forecast_club') and item.custom_forecast_club:
			forecast_clubs.add(item.custom_forecast_club)

	# Update status for each Forecast Club
	for fc_name in forecast_clubs:
		# Check if there are any other non-cancelled Material Requests for this Forecast Club
		other_mrs = frappe.db.count(
			"Material Request Item",
			filters={
				"custom_forecast_club": fc_name,
				"docstatus": ["!=", 2],  # Not cancelled
				"parent": ["!=", doc.name]  # Not the current document
			}
		)

		# If no other Material Requests exist, reset status to Forecast Planned
		if other_mrs == 0:
			frappe.db.set_value("Forecast Club", fc_name, "status", "Forecast Planned")
