from odoo import api, fields, models, _


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _reconcile_account_move_lines(self, data):
        # reconcile cash receivable lines
        split_cash_statement_lines = data.get('split_cash_statement_lines')
        combine_cash_statement_lines = data.get('combine_cash_statement_lines')
        split_cash_receivable_lines = data.get('split_cash_receivable_lines')
        combine_cash_receivable_lines = data.get('combine_cash_receivable_lines')
        order_account_move_receivable_lines = data.get('order_account_move_receivable_lines')
        invoice_receivable_lines = data.get('invoice_receivable_lines')
        stock_output_lines = data.get('stock_output_lines')

        for statement in self.statement_ids:
            if not self.config_id.cash_control:
                statement.write({'balance_end_real': statement.balance_end})
            statement.button_confirm_bank()
            all_lines = (
                    split_cash_statement_lines[statement].mapped('journal_entry_ids').filtered(
                        lambda aml: aml.account_id.internal_type == 'receivable')
                    | combine_cash_statement_lines[statement].mapped('journal_entry_ids').filtered(
                lambda aml: aml.account_id.internal_type == 'receivable')
                    | split_cash_receivable_lines[statement]
                    | combine_cash_receivable_lines[statement]
            )
            accounts = all_lines.mapped('account_id')
            lines_by_account = [all_lines.filtered(lambda l: l.account_id == account) for account in accounts]
            for lines in lines_by_account:
                lines.reconcile()

        # reconcile invoice receivable lines
        for account_id in order_account_move_receivable_lines:
            (order_account_move_receivable_lines[account_id]
             | invoice_receivable_lines.get(account_id, self.env['account.move.line'])
             ).reconcile()

        # reconcile stock output lines
        orders_to_invoice = self.order_ids.filtered(lambda order: not order.is_invoiced)
        stock_moves = (
                orders_to_invoice.mapped('picking_id') +
                self.env['stock.picking'].search(
                    [('origin', 'in', orders_to_invoice.mapped(lambda o: '%s - %s' % (self.name, o.name)))])
        ).mapped('move_lines')
        stock_account_move_lines = self.env['account.move'].search([('stock_move_id', 'in', stock_moves.ids)]).mapped(
            'line_ids')
        for account_id in stock_output_lines:
            (stock_output_lines[account_id].filtered(lambda aml: not aml.reconciled)
             | stock_account_move_lines.filtered(lambda aml: aml.account_id == account_id and not aml.reconciled)  # only change from standard
             ).reconcile()
        return data