import 'package:flutter/material.dart';

import '../data.dart';
import '../kit.dart';
import '../theme.dart';

class ProfileTab extends StatelessWidget {
  const ProfileTab({super.key});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return PageBody(
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(Tk.l),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: Tk.brandSoft,
                    shape: BoxShape.circle,
                    border: Border.all(color: Tk.line),
                  ),
                  child: const Icon(Icons.person_outline, color: Tk.brand),
                ),
                const SizedBox(width: Tk.m),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Demo account',
                        key: const Key('profile_name'),
                        style: text.titleMedium,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        Store.instance.email.isEmpty
                            ? 'demo@example.com'
                            : Store.instance.email,
                        key: const Key('profile_email'),
                        style: text.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: Tk.xl),
        const SectionHeader(
          'Account',
          subtitle: 'Where things ship and how you pay.',
        ),
        identified(
          'profile_addresses',
          RowCard(
            key: const Key('profile_addresses'),
            icon: Icons.location_on_outlined,
            title: 'Addresses',
            subtitle: '${Store.instance.addresses.length} saved',
            onTap: () => Navigator.of(
              context,
            ).push(MaterialPageRoute(builder: (_) => const AddressesScreen())),
          ),
        ),
        const SizedBox(height: Tk.m),
        identified(
          'profile_payments',
          RowCard(
            key: const Key('profile_payments'),
            icon: Icons.credit_card,
            title: 'Payment methods',
            subtitle: '${Store.instance.payments.length} saved',
            onTap: () => Navigator.of(
              context,
            ).push(MaterialPageRoute(builder: (_) => const PaymentsScreen())),
          ),
        ),
        const SizedBox(height: Tk.xl),
        const SectionHeader('Preferences'),
        identified(
          'profile_notifications',
          RowCard(
            key: const Key('profile_notifications'),
            icon: Icons.notifications_none,
            title: 'Notifications',
            subtitle: 'Email, push and return reminders',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const NotificationsScreen()),
            ),
          ),
        ),
        const SizedBox(height: Tk.m),
        identified(
          'profile_developer',
          RowCard(
            key: const Key('profile_developer'),
            icon: Icons.build_outlined,
            title: 'Developer settings',
            subtitle: 'Simulate slow loads and failures',
            onTap: () => Navigator.of(
              context,
            ).push(MaterialPageRoute(builder: (_) => const DeveloperScreen())),
          ),
        ),
        const SizedBox(height: Tk.xl),
        identified(
          'profile_signout',
          Card(
            child: InkWell(
              key: const Key('profile_signout'),
              borderRadius: BorderRadius.circular(Tk.radius),
              onTap: () => _confirmSignOut(context),
              child: Padding(
                padding: const EdgeInsets.all(Tk.l),
                child: Row(
                  children: [
                    const Icon(Icons.logout, size: 20, color: Tk.danger),
                    const SizedBox(width: Tk.m),
                    Text(
                      'Sign out',
                      style: text.titleMedium?.copyWith(color: Tk.danger),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  void _confirmSignOut(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Sign out of this device?'),
        content: const Text('Your cart and saved details stay on the account.'),
        actions: [
          identified(
            'signout_cancel',
            TextButton(
              key: const Key('signout_cancel'),
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Stay signed in'),
            ),
          ),
          identified(
            'signout_confirm',
            FilledButton(
              key: const Key('signout_confirm'),
              style: FilledButton.styleFrom(
                backgroundColor: Tk.danger,
                minimumSize: const Size(0, 44),
              ),
              onPressed: () {
                Navigator.of(dialogContext).pop();
                // Back to the first route, whatever it is — this file does not
                // know about the sign-in screen.
                Navigator.of(context).popUntil((route) => route.isFirst);
              },
              child: const Text('Sign out'),
            ),
          ),
        ],
      ),
    );
  }
}

class AddressesScreen extends StatelessWidget {
  const AddressesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Addresses')),
      body: ListenableBuilder(
        listenable: Store.instance,
        builder: (context, _) => PageBody(
          children: [
            const SectionHeader(
              'Saved addresses',
              subtitle: 'The default one is used at checkout.',
            ),
            for (final address in Store.instance.addresses) ...[
              identified(
                'address_${address.id}',
                RowCard(
                  key: Key('address_${address.id}'),
                  icon: Icons.location_on_outlined,
                  title: address.label,
                  subtitle: address.lines.replaceAll('\n', ', '),
                  pill: address.isDefault
                      ? const StatusPill('Default', tone: Tone.good)
                      : null,
                  onTap: () => _openSheet(context, address),
                ),
              ),
              const SizedBox(height: Tk.m),
            ],
            const SizedBox(height: Tk.s),
            identified(
              'add_address_button',
              OutlinedButton.icon(
                key: const Key('add_address_button'),
                onPressed: () => _openSheet(context, null),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add an address'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _openSheet(BuildContext context, Address? address) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (_) => _AddressSheet(address: address),
    );
  }
}

class _AddressSheet extends StatefulWidget {
  const _AddressSheet({this.address});

  final Address? address;

  @override
  State<_AddressSheet> createState() => _AddressSheetState();
}

class _AddressSheetState extends State<_AddressSheet> {
  late final TextEditingController _label = TextEditingController(
    text: widget.address?.label ?? '',
  );
  late final TextEditingController _lines = TextEditingController(
    text: widget.address?.lines ?? '',
  );
  late bool _isDefault = widget.address?.isDefault ?? false;
  String? _error;

  @override
  void dispose() {
    _label.dispose();
    _lines.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.address != null;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        Tk.xl,
        0,
        Tk.xl,
        Tk.xxl + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            editing ? 'Edit address' : 'Add an address',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: Tk.l),
          identified(
            'address_label_field',
            TextField(
              key: const Key('address_label_field'),
              controller: _label,
              decoration: const InputDecoration(
                labelText: 'Label',
                hintText: 'Home, Workshop, Parents',
              ),
            ),
          ),
          const SizedBox(height: Tk.m),
          identified(
            'address_lines_field',
            TextField(
              key: const Key('address_lines_field'),
              controller: _lines,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Address'),
            ),
          ),
          const SizedBox(height: Tk.s),
          identified(
            'address_default_switch',
            SwitchListTile(
              key: const Key('address_default_switch'),
              value: _isDefault,
              onChanged: (v) => setState(() => _isDefault = v),
              title: const Text('Set as default'),
              contentPadding: EdgeInsets.zero,
              dense: true,
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: Tk.s),
            Text(
              _error!,
              key: const Key('address_error'),
              style: Theme.of(context).textTheme.bodySmall
                  ?.copyWith(color: Tk.danger),
            ),
          ],
          const SizedBox(height: Tk.l),
          identified(
            'address_save_button',
            FilledButton(
              key: const Key('address_save_button'),
              onPressed: () {
                final label = _label.text.trim();
                final lines = _lines.text.trim();
                if (label.isEmpty || lines.isEmpty) {
                  setState(
                    () => _error =
                        'Both a label and an address are '
                        'needed.',
                  );
                  return;
                }
                if (editing) {
                  Store.instance.updateAddress(
                    widget.address!.id,
                    label,
                    lines,
                    makeDefault: _isDefault,
                  );
                } else {
                  Store.instance.addAddress(
                    label,
                    lines,
                    makeDefault: _isDefault,
                  );
                }
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      editing ? 'Address updated.' : 'Address added.',
                    ),
                    duration: const Duration(seconds: 2),
                  ),
                );
              },
              child: const Text('Save address'),
            ),
          ),
        ],
      ),
    );
  }
}

class PaymentsScreen extends StatelessWidget {
  const PaymentsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment methods')),
      body: ListenableBuilder(
        listenable: Store.instance,
        builder: (context, _) => PageBody(
          children: [
            const SectionHeader(
              'Saved methods',
              subtitle: 'Charged when an order ships.',
            ),
            for (final payment in Store.instance.payments) ...[
              identified(
                'payment_${payment.id}',
                RowCard(
                  key: Key('payment_${payment.id}'),
                  icon: payment.icon,
                  title: payment.label,
                  subtitle: payment.detail,
                  pill: payment.isDefault
                      ? const StatusPill('Default', tone: Tone.good)
                      : null,
                ),
              ),
              const SizedBox(height: Tk.m),
            ],
            const SizedBox(height: Tk.s),
            identified(
              'add_payment_button',
              OutlinedButton.icon(
                key: const Key('add_payment_button'),
                onPressed: () => showModalBottomSheet<void>(
                  context: context,
                  showDragHandle: true,
                  isScrollControlled: true,
                  builder: (_) => const _CardSheet(),
                ),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add a card'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CardSheet extends StatefulWidget {
  const _CardSheet();

  @override
  State<_CardSheet> createState() => _CardSheetState();
}

class _CardSheetState extends State<_CardSheet> {
  final _number = TextEditingController();
  final _expiry = TextEditingController();
  final _cvc = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _number.dispose();
    _expiry.dispose();
    _cvc.dispose();
    super.dispose();
  }

  void _save() {
    final number = _number.text.trim();
    if (number.isEmpty) {
      setState(() => _error = 'Enter a card number.');
      return;
    }
    final last4 = number.length >= 4
        ? number.substring(number.length - 4)
        : number;
    final expiry = _expiry.text.trim();
    Store.instance.addPayment(
      'Card ·· $last4',
      expiry.isEmpty ? 'No expiry given' : 'Expires $expiry',
    );
    Navigator.of(context).pop();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Card added.'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        Tk.xl,
        0,
        Tk.xl,
        Tk.xxl + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Add a card', style: text.titleLarge),
          const SizedBox(height: Tk.s),
          Text('Demo build · nothing is sent anywhere.', style: text.bodySmall),
          const SizedBox(height: Tk.l),
          identified(
            'card_number_field',
            TextField(
              key: const Key('card_number_field'),
              controller: _number,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Card number',
                prefixIcon: Icon(Icons.credit_card, size: 19),
              ),
            ),
          ),
          const SizedBox(height: Tk.m),
          Row(
            children: [
              Expanded(
                child: identified(
                  'card_expiry_field',
                  TextField(
                    key: const Key('card_expiry_field'),
                    controller: _expiry,
                    decoration: const InputDecoration(
                      labelText: 'Expiry',
                      hintText: 'MM/YY',
                    ),
                  ),
                ),
              ),
              const SizedBox(width: Tk.m),
              Expanded(
                child: identified(
                  'card_cvc_field',
                  TextField(
                    key: const Key('card_cvc_field'),
                    controller: _cvc,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'CVC'),
                  ),
                ),
              ),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: Tk.m),
            Container(
              key: const Key('card_error'),
              padding: const EdgeInsets.all(Tk.m),
              decoration: BoxDecoration(
                color: Tk.dangerSoft,
                borderRadius: BorderRadius.circular(Tk.radiusSm),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, size: 18, color: Tk.danger),
                  const SizedBox(width: Tk.s),
                  Expanded(
                    child: Text(
                      _error!,
                      style: text.bodySmall?.copyWith(color: Tk.danger),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: Tk.l),
          identified(
            'card_save_button',
            FilledButton(
              key: const Key('card_save_button'),
              onPressed: _save,
              child: const Text('Save card'),
            ),
          ),
        ],
      ),
    );
  }
}

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final store = Store.instance;
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: ListenableBuilder(
        listenable: store,
        builder: (context, _) => PageBody(
          children: [
            const SectionHeader(
              'What we send you',
              subtitle: 'Changes apply to this account straight away.',
            ),
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: Tk.s,
                  vertical: Tk.xs,
                ),
                child: Column(
                  children: [
                    identified(
                      'notify_email_switch',
                      SwitchListTile(
                        key: const Key('notify_email_switch'),
                        value: store.emailUpdates,
                        onChanged: (v) => store.toggle('email', v),
                        title: const Text('Email updates'),
                        subtitle: const Text(
                          'Order confirmations and receipts',
                        ),
                      ),
                    ),
                    const Divider(),
                    identified(
                      'notify_push_switch',
                      SwitchListTile(
                        key: const Key('notify_push_switch'),
                        value: store.pushUpdates,
                        onChanged: (v) => store.toggle('push', v),
                        title: const Text('Push notifications'),
                        subtitle: const Text(
                          'Delivery progress on this device',
                        ),
                      ),
                    ),
                    const Divider(),
                    identified(
                      'notify_returns_switch',
                      SwitchListTile(
                        key: const Key('notify_returns_switch'),
                        value: store.returnReminders,
                        onChanged: (v) => store.toggle('returns', v),
                        title: const Text('Return reminders'),
                        subtitle: const Text(
                          'A nudge before a return window closes',
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The failure-path switches. An agent flips these to test the slow and broken
/// branches instead of waiting for them to happen by chance.
class DeveloperScreen extends StatelessWidget {
  const DeveloperScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final store = Store.instance;
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Developer settings')),
      body: ListenableBuilder(
        listenable: store,
        builder: (context, _) => PageBody(
          children: [
            const SectionHeader(
              'Simulate conditions',
              subtitle: 'These stay on until you turn them off.',
            ),
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: Tk.s,
                  vertical: Tk.xs,
                ),
                child: Column(
                  children: [
                    identified(
                      'dev_slow_network_switch',
                      SwitchListTile(
                        key: const Key('dev_slow_network_switch'),
                        value: store.simulateSlowNetwork,
                        onChanged: (v) => store.toggle('slow', v),
                        title: const Text('Slow network'),
                        subtitle: const Text(
                          'Adds about 2 seconds to every load in the app',
                        ),
                      ),
                    ),
                    const Divider(),
                    identified(
                      'dev_orders_error_switch',
                      SwitchListTile(
                        key: const Key('dev_orders_error_switch'),
                        value: store.simulateOrdersError,
                        onChanged: (v) => store.toggle('error', v),
                        title: const Text('Orders request fails'),
                        subtitle: const Text(
                          'The orders list will fail to load and show a retry',
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: Tk.xl),
            Card(
              key: const Key('dev_state_card'),
              child: Padding(
                padding: const EdgeInsets.all(Tk.l),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Current state', style: text.titleMedium),
                    const SizedBox(height: Tk.m),
                    _StateLine('Slow network', store.simulateSlowNetwork),
                    _StateLine('Orders error', store.simulateOrdersError),
                    _StateLine('Email updates', store.emailUpdates),
                    _StateLine('Push notifications', store.pushUpdates),
                    _StateLine('Return reminders', store.returnReminders),
                    const SizedBox(height: Tk.s),
                    Text(
                      'Request latency · ${store.latency.inMilliseconds} ms',
                      style: text.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StateLine extends StatelessWidget {
  const _StateLine(this.label, this.value);

  final String label;
  final bool value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Tk.s),
      child: Row(
        children: [
          Expanded(
            child: Text(label, style: Theme.of(context).textTheme.bodyMedium),
          ),
          StatusPill(
            value ? 'On' : 'Off',
            tone: value ? Tone.warn : Tone.neutral,
          ),
        ],
      ),
    );
  }
}
