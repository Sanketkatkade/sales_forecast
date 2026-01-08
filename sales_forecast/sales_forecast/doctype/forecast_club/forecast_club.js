// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Forecast Club", {
	refresh(frm) {
		if (frm.doc.docstatus === 1
			&& frm.doc.material_request_items
			&& frm.doc.material_request_items.length > 0
			&& frm.doc.status === "Forecast Planned") {

			frm.add_custom_button(__('Create Material Request'), function() {
				frm.call({
					method: 'create_material_requests',
					doc: frm.doc,
					freeze: true,
					freeze_message: __('Creating Material Request...'),
					callback: function(r) {
						if (!r.exc && r.message) {
							frappe.show_alert({
								message: __('Material Request created successfully'),
								indicator: 'green'
							});
							frm.reload_doc();
						}
					}
				});
			});
		}
	},

	validate(frm) {
		validate_week_and_batch_fields(frm);
	},

	get_fetch_material_request_item(frm) {
		frm.call({
			method: 'fetch_material_request_items',
			doc: frm.doc,
			freeze: true,
			freeze_message: __('Fetching material request items...'),
			callback: function(r) {
				if (!r.exc) {
					frm.refresh_field('material_request_items');
					frm.save().then(() => {
						frappe.show_alert({
							message: __('Material Request Items fetched successfully'),
							indicator: 'green'
						});
					});
				}
			}
		});
	},

	forecast_start_date(frm) {
		fetch_sales_forecasts_if_dates_set(frm);
	},

	forecast_end_date(frm) {
		fetch_sales_forecasts_if_dates_set(frm);
	},

	company(frm) {
		fetch_sales_forecasts_if_dates_set(frm);
	}
});

function validate_week_and_batch_fields(frm) {
	const week_batch_mapping = [
		{ week: 'week_1', batch: 'w1_batch', label: 'Week 1' },
		{ week: 'week_2', batch: 'w2_batch', label: 'Week 2' },
		{ week: 'week_3', batch: 'w3_batch', label: 'Week 3' },
		{ week: 'week_4', batch: 'w4_batch', label: 'Week 4' }
	];

	let errors = [];

	frm.doc.items.forEach((row, idx) => {
		week_batch_mapping.forEach(mapping => {
			const week_value = row[mapping.week] || 0;
			const batch_value = row[mapping.batch] || 0;

			// If week value is 0 or empty, batch must also be 0 or empty
			if (week_value === 0 || !week_value) {
				// Week is 0/empty, batch should be 0/empty - this is valid
				// No error needed
			} else {
				// Week has a value greater than 0
				// Batch must also be greater than 0
				if (batch_value === 0 || !batch_value) {
					errors.push(__('Row {0}: {1} has value {2}, but {3} Batch is 0 or empty. Batch is required when week value is greater than 0.',
						[idx + 1, mapping.label, week_value, mapping.label]));
				}
			}
		});
	});

	if (errors.length > 0) {
		frappe.msgprint({
			title: __('Validation Error'),
			indicator: 'red',
			message: errors.join('<br>')
		});
		frappe.validated = false;
	}
}

function fetch_sales_forecasts_if_dates_set(frm) {
	// Only fetch if all required fields are set
	if (frm.doc.forecast_start_date && frm.doc.forecast_end_date && frm.doc.company) {
		frm.call({
			method: 'fetch_sales_forecasts',
			doc: frm.doc,
			freeze: true,
			freeze_message: __('Fetching sales forecasts...'),
			callback: function(r) {
				if (!r.exc) {
					frm.refresh_field('items');
					frappe.show_alert({
						message: __('Sales Forecasts fetched successfully'),
						indicator: 'green'
					});
				}
			}
		});
	}
}

frappe.ui.form.on("Forecast Club Item", {
	batch_size(frm, cdt, cdn) {
		calculate_totals(frm, cdt, cdn);
	},

	week_1(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_1', 'w1_batch', 'Week 1');
	},

	week_2(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_2', 'w2_batch', 'Week 2');
	},

	week_3(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_3', 'w3_batch', 'Week 3');
	},

	week_4(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_4', 'w4_batch', 'Week 4');
	},

	w1_batch(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_1', 'w1_batch', 'Week 1');
		calculate_totals(frm, cdt, cdn);
	},

	w2_batch(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_2', 'w2_batch', 'Week 2');
		calculate_totals(frm, cdt, cdn);
	},

	w3_batch(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_3', 'w3_batch', 'Week 3');
		calculate_totals(frm, cdt, cdn);
	},

	w4_batch(frm, cdt, cdn) {
		validate_week_batch_relationship(frm, cdt, cdn, 'week_4', 'w4_batch', 'Week 4');
		calculate_totals(frm, cdt, cdn);
	}
});

function validate_week_batch_relationship(frm, cdt, cdn, week_field, batch_field, week_label) {
	let row = locals[cdt][cdn];
	const week_value = row[week_field] || 0;
	const batch_value = row[batch_field] || 0;

	// If week value is greater than 0, batch must also be greater than 0
	if (week_value > 0 && batch_value === 0) {
		frappe.msgprint({
			title: __('Validation Error'),
			indicator: 'orange',
			message: __('{0} has a value of {1}, but {2} Batch is 0 or empty. Please enter a batch value when week value is greater than 0.',
				[week_label, week_value, week_label])
		});
	}
}

function calculate_totals(frm, cdt, cdn) {
	let row = locals[cdt][cdn];

	// Calculate total_batch_qty as sum of all weekly batches
	row.total_batch_qty = (row.w1_batch || 0) + (row.w2_batch || 0) + (row.w3_batch || 0) + (row.w4_batch || 0);

	// Calculate total_qty as total_batch_qty * batch_size
	row.total_qty = row.total_batch_qty * (row.batch_size || 0);

	frm.refresh_field('items');
}
