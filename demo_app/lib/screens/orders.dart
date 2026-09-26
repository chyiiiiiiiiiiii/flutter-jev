import 'dart:math';

import 'package:flutter/material.dart';

import '../data.dart';
import '../kit.dart';
import '../theme.dart';

Tone _toneFor(OrderStatus s) => switch (s) {
  OrderStatus.delivered => Tone.good,
  OrderStatus.inTransit || OrderStatus.processing => Tone.warn,
  OrderStatus.cancelled => Tone.bad,
  OrderStatus.returning || OrderStatus.refunded => Tone.neutral,
};

class OrdersTab extends StatefulWidget {
  const OrdersTab({super.key});

  @override
  State<OrdersTab> createState() => _OrdersTabState();
}

class _OrdersTabState extends State<OrdersTab> {
  static const _filters = <String, Set<OrderStatus>>{
    'orders_filter_all': {},
    'orders_filter_open': {OrderStatus.processing, OrderStatus.inTransit},
    'orders_filter_delivered': {OrderStatus.delivered},
    'orders_filter_returns': {OrderStatus.returning, OrderStatus.refunded},
  };

  final _search = TextEditingController();
  String _filter = 'orders_filter_all';
  bool _loading = true;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _failed = false;
    });
    await Future<void>.delayed(Store.instance.latency);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _failed = Store.instance.simulateOrdersError;
    });
  }

  List<Order> get _visible {
    final wanted = _filters[_filter]!;
    final query = _search.text.trim().toLowerCase();
    return Store.instance.orders.where((o) {
      if (wanted.isNotEmpty && !wanted.contains(o.status)) return false;
      if (query.isEmpty) return true;
      return o.id.contains(query) ||
          o.items.any((i) => i.name.toLowerCase().contains(query));
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Store.instance,
      builder: (context, _) {
        final orders = _visible;
        return Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: Tk.maxContent),
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(Tk.l, Tk.l, Tk.l, Tk.s),
                  child: Column(
                    children: [
                      const SectionHeader(
                        'Your orders',
                        subtitle:
                            'Track a delivery, start a return, or cancel.',
                      ),
                      identified(
                        'orders_search',
                        TextField(
                          key: const Key('orders_search'),
                          controller: _search,
                          onChanged: (_) => setState(() {}),
                          decoration: InputDecoration(
                            hintText: 'Search by item or order number',
                            prefixIcon: const Icon(Icons.search, size: 19),
                            suffixIcon: _search.text.isEmpty
                                ? null
                                : identified(
                                    'orders_search_clear',
                                    IconButton(
                                      key: const Key('orders_search_clear'),
                                      icon: const Icon(Icons.close, size: 18),
                                      tooltip: 'Clear search',
                                      onPressed: () {
                                        _search.clear();
                                        setState(() {});
                                      },
                                    ),
                                  ),
                          ),
                        ),
                      ),
                      const SizedBox(height: Tk.m),
                      SizedBox(
                        height: 36,
                        child: ListView(
                          scrollDirection: Axis.horizontal,
                          children: [
                            for (final entry in _filters.entries)
                              Padding(
                                padding: const EdgeInsets.only(right: Tk.s),
                                child: identified(
                                  entry.key,
                                  FilterChip(
                                    key: Key(entry.key),
                                    label: Text(_filterLabel(entry.key)),
                                    selected: _filter == entry.key,
                                    showCheckmark: false,
                                    selectedColor: Tk.brandSoft,
                                    side: const BorderSide(color: Tk.line),
                                    onSelected: (_) =>
                                        setState(() => _filter = entry.key),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(child: _body(orders)),
              ],
            ),
          ),
        );
      },
    );
  }

  String _filterLabel(String key) => switch (key) {
    'orders_filter_open' => 'Open',
    'orders_filter_delivered' => 'Delivered',
    'orders_filter_returns' => 'Returns',
    _ => 'All',
  };

  /// Chaos reorders what is on screen without changing what is on screen.
  /// Applying it instead of the filtered list, as a first attempt did, quietly
  /// disabled search entirely; the widget test caught it.
  List<Order> _ordered(List<Order> filtered) {
    if (!Store.instance.chaos) return filtered;
    return [...filtered]..shuffle(Random(Store.instance.chaosSeed));
  }

  Widget _body(List<Order> orders) {
    if (_loading) {
      return const Padding(padding: EdgeInsets.all(Tk.l), child: LoadingList());
    }
    if (_failed) {
      return EmptyState(
        key: const Key('orders_error'),
        icon: Icons.cloud_off_outlined,
        title: 'We could not load your orders',
        body: 'The request failed. Check your connection and try again.',
        action: identified(
          'orders_retry_button',
          OutlinedButton.icon(
            key: const Key('orders_retry_button'),
            onPressed: _load,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Try again'),
          ),
        ),
      );
    }
    if (orders.isEmpty) {
      return const EmptyState(
        key: Key('orders_empty'),
        icon: Icons.receipt_long_outlined,
        title: 'Nothing here yet',
        body: 'No order matches that search or filter.',
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(Tk.l, Tk.s, Tk.l, Tk.xxl),
        children: [
          for (final order in _ordered(orders))
            Padding(
              padding: const EdgeInsets.only(bottom: Tk.m),
              child: identified(
                Store.instance.k('order_${order.id}'),
                RowCard(
                  key: Key(Store.instance.k('order_${order.id}')),
                  icon: order.items.first.icon,
                  title: order.title,
                  subtitle: 'Order #${order.id} · placed ${order.placed}',
                  meta: money(order.totalCents),
                  pill: StatusPill(
                    order.status.label,
                    tone: _toneFor(order.status),
                  ),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => OrderDetailScreen(orderId: order.id),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class OrderDetailScreen extends StatelessWidget {
  const OrderDetailScreen({required this.orderId, super.key});

  final String orderId;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Store.instance,
      builder: (context, _) {
        final order = Store.instance.orderById(orderId);
        final text = Theme.of(context).textTheme;
        return Scaffold(
          appBar: AppBar(title: Text('Order #${order.id}')),
          body: PageBody(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Everything in one place.',
                      style: text.headlineSmall,
                    ),
                  ),
                  StatusPill(order.status.label, tone: _toneFor(order.status)),
                ],
              ),
              const SizedBox(height: Tk.xs),
              Text(
                'Placed ${order.placed} · ${order.carrier}',
                style: text.bodySmall,
              ),
              const SizedBox(height: Tk.l),
              Card(
                child: Column(
                  children: [
                    for (final item in order.items) ...[
                      ListTile(
                        leading: Icon(item.icon, color: Tk.brand),
                        title: Text(item.name, style: text.titleMedium),
                        subtitle: Text('${item.variant} · qty ${item.qty}'),
                        trailing: Text(
                          money(item.totalCents),
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                      if (item != order.items.last) const Divider(),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: Tk.m),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(Tk.l),
                  child: Column(
                    children: [
                      _row(context, 'Subtotal', money(order.subtotalCents)),
                      const SizedBox(height: Tk.s),
                      _row(
                        context,
                        'Shipping',
                        order.shippingCents == 0
                            ? 'Free'
                            : money(order.shippingCents),
                      ),
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: Tk.m),
                        child: Divider(),
                      ),
                      _row(
                        context,
                        'Total',
                        money(order.totalCents),
                        bold: true,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: Tk.m),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(Tk.l),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Delivery', style: text.titleMedium),
                      const SizedBox(height: Tk.xs),
                      Text(order.address, style: text.bodySmall),
                      const SizedBox(height: Tk.m),
                      Text('Payment', style: text.titleMedium),
                      const SizedBox(height: Tk.xs),
                      Text(order.paymentLabel, style: text.bodySmall),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: Tk.xl),
              identified(
                'track_order_button',
                OutlinedButton.icon(
                  key: const Key('track_order_button'),
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => TrackingScreen(orderId: order.id),
                    ),
                  ),
                  icon: const Icon(Icons.local_shipping_outlined, size: 18),
                  label: const Text('Track this order'),
                ),
              ),
              const SizedBox(height: Tk.m),
              identified(
                Store.instance.k('start_return_button'),
                FilledButton.icon(
                  key: Key(Store.instance.k('start_return_button')),
                  onPressed: order.status.returnable
                      ? () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => ReturnFlowScreen(orderId: order.id),
                          ),
                        )
                      : null,
                  icon: const Icon(Icons.keyboard_return, size: 18),
                  label: Text(
                    order.status.returnable
                        ? Store.instance.label('Start a return')
                        : _returnLabel(order.status),
                  ),
                ),
              ),
              if (order.status == OrderStatus.returning ||
                  order.status == OrderStatus.refunded) ...[
                const SizedBox(height: Tk.m),
                identified(
                  'refund_status_button',
                  OutlinedButton.icon(
                    key: const Key('refund_status_button'),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => RefundStatusScreen(orderId: order.id),
                      ),
                    ),
                    icon: const Icon(
                      Icons.assignment_return_outlined,
                      size: 18,
                    ),
                    label: const Text('Refund status'),
                  ),
                ),
              ],
              if (order.status.cancellable) ...[
                const SizedBox(height: Tk.m),
                identified(
                  'cancel_order_button',
                  TextButton(
                    key: const Key('cancel_order_button'),
                    onPressed: () => _confirmCancel(context, order.id),
                    style: TextButton.styleFrom(foregroundColor: Tk.danger),
                    child: const Text('Cancel this order'),
                  ),
                ),
              ],
              const SizedBox(height: Tk.xxl),
            ],
          ),
        );
      },
    );
  }

  static String _returnLabel(OrderStatus s) => switch (s) {
    OrderStatus.delivered => 'Start a return',
    OrderStatus.returning => 'Return already in progress',
    OrderStatus.refunded => 'Already refunded',
    OrderStatus.cancelled => 'Order was cancelled',
    _ => 'Return available after delivery',
  };

  static Widget _row(
    BuildContext c,
    String left,
    String right, {
    bool bold = false,
  }) {
    final style = bold
        ? const TextStyle(fontWeight: FontWeight.w700, color: Tk.ink)
        : Theme.of(c).textTheme.bodyMedium;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(left, style: style),
        Text(right, style: style),
      ],
    );
  }

  Future<void> _confirmCancel(BuildContext context, String id) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel this order?'),
        content: const Text(
          'It has not shipped yet, so we can stop it. This cannot be undone.',
        ),
        actions: [
          identified(
            'cancel_dismiss',
            TextButton(
              key: const Key('cancel_dismiss'),
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Keep the order'),
            ),
          ),
          identified(
            'cancel_confirm',
            FilledButton(
              key: const Key('cancel_confirm'),
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('Cancel it'),
            ),
          ),
        ],
      ),
    );
    if (yes ?? false) {
      Store.instance.cancelOrder(id);
    }
  }
}

class TrackingScreen extends StatelessWidget {
  const TrackingScreen({required this.orderId, super.key});

  final String orderId;

  @override
  Widget build(BuildContext context) {
    final order = Store.instance.orderById(orderId);
    final delivered = order.status == OrderStatus.delivered;
    final shipped = delivered || order.status == OrderStatus.inTransit;
    return Scaffold(
      appBar: AppBar(title: const Text('Tracking')),
      body: PageBody(
        children: [
          Text(
            delivered ? 'Your order has arrived.' : 'On its way to you.',
            key: const Key('tracking_headline'),
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: Tk.xs),
          Text(
            '${order.carrier} · ${order.trackingNo ?? 'pending'}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: Tk.xl),
          Timeline(
            steps: [
              const TimelineStep(
                'Order confirmed',
                'We received your order and took payment.',
                done: true,
              ),
              TimelineStep(
                'Packed',
                shipped ? 'Left the warehouse.' : 'Being picked now.',
                done: shipped,
              ),
              TimelineStep(
                'Out for delivery',
                shipped ? 'Handed to the courier.' : 'Not yet scheduled.',
                done: shipped,
              ),
              TimelineStep(
                'Delivered',
                delivered
                    ? 'Delivered ${order.deliveredDaysAgo} days ago.'
                    : 'Estimated in 2 days.',
                done: delivered,
              ),
            ],
          ),
          identified(
            'copy_tracking_button',
            OutlinedButton.icon(
              key: const Key('copy_tracking_button'),
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Tracking number copied.'),
                  duration: Duration(seconds: 2),
                ),
              ),
              icon: const Icon(Icons.copy_outlined, size: 18),
              label: const Text('Copy tracking number'),
            ),
          ),
        ],
      ),
    );
  }
}

/// A three-step return, because a single-screen form does not exercise the
/// thing that actually breaks test suites: state carried across steps.
class ReturnFlowScreen extends StatefulWidget {
  const ReturnFlowScreen({required this.orderId, super.key});

  final String orderId;

  @override
  State<ReturnFlowScreen> createState() => _ReturnFlowScreenState();
}

class _ReturnFlowScreenState extends State<ReturnFlowScreen> {
  static const reasons = [
    'Item arrived damaged',
    'Wrong size or fit',
    'Not what I expected',
    'No longer needed',
  ];
  static const resolutions = ['Refund to card', 'Store credit'];

  int _step = 0;
  String _reason = reasons.first;
  final _notes = TextEditingController();
  final _picked = <String>{};
  String _resolution = resolutions.first;
  bool _understood = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final order = Store.instance.orderById(widget.orderId);
    _picked.add(order.items.first.name);
  }

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  bool get _canAdvance => switch (_step) {
    0 => _picked.isNotEmpty,
    1 => true,
    _ => _understood,
  };

  Future<void> _next() async {
    if (_step < 2) {
      setState(() => _step++);
      return;
    }
    setState(() => _busy = true);
    await Future<void>.delayed(Store.instance.latency);
    if (!mounted) return;
    Store.instance.startReturn(widget.orderId);
    await Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => ReturnDoneScreen(orderId: widget.orderId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final order = Store.instance.orderById(widget.orderId);
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: Text('Return · step ${_step + 1} of 3'),
        leading: identified(
          'return_back_button',
          IconButton(
            key: const Key('return_back_button'),
            icon: const Icon(Icons.arrow_back),
            tooltip: 'Back',
            onPressed: () => _step == 0
                ? Navigator.of(context).pop()
                : setState(() => _step--),
          ),
        ),
      ),
      body: PageBody(
        children: [
          LinearProgressIndicator(
            value: (_step + 1) / 3,
            backgroundColor: Tk.line,
            color: Tk.brand,
            minHeight: 3,
          ),
          const SizedBox(height: Tk.xl),
          Text(_headline(), style: text.headlineSmall),
          const SizedBox(height: Tk.xs),
          Text(_blurb(order), style: text.bodyMedium),
          const SizedBox(height: Tk.xl),
          ..._stepBody(order),
          const SizedBox(height: Tk.xl),
          identified(
            Store.instance.k('return_next_button'),
            FilledButton(
              key: Key(Store.instance.k('return_next_button')),
              onPressed: _canAdvance && !_busy ? _next : null,
              child: _busy
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : Text(
                      Store.instance.label(
                        _step == 2 ? 'Submit return request' : 'Continue',
                      ),
                    ),
            ),
          ),
          const SizedBox(height: Tk.xxl),
        ],
      ),
    );
  }

  String _headline() => switch (_step) {
    0 => "Let's make this right.",
    1 => 'Tell us what happened.',
    _ => 'Check and confirm.',
  };

  String _blurb(Order order) => switch (_step) {
    0 => 'Choose the items you want to send back.',
    1 => 'A reason helps us fix the root cause.',
    _ =>
      'Delivered ${order.deliveredDaysAgo} days ago · '
          'within the 30 day window.',
  };

  List<Widget> _stepBody(Order order) => switch (_step) {
    0 => [
      for (final item in order.items)
        identified(
          'return_item_${order.items.indexOf(item)}',
          CheckboxListTile(
            key: Key('return_item_${order.items.indexOf(item)}'),
            value: _picked.contains(item.name),
            onChanged: (v) => setState(() {
              if (v ?? false) {
                _picked.add(item.name);
              } else {
                _picked.remove(item.name);
              }
            }),
            title: Text(item.name),
            subtitle: Text('${item.variant} · ${money(item.totalCents)}'),
            controlAffinity: ListTileControlAffinity.leading,
          ),
        ),
      if (_picked.isEmpty)
        Padding(
          padding: const EdgeInsets.only(top: Tk.s),
          child: Text(
            'Pick at least one item to continue.',
            key: const Key('return_no_items_hint'),
            style: Theme.of(context).textTheme.bodySmall
                ?.copyWith(color: Tk.danger),
          ),
        ),
    ],
    1 => [
      identified(
        'return_reason',
        DropdownButtonFormField<String>(
          key: const Key('return_reason'),
          initialValue: _reason,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Reason for return'),
          items: [
            for (final r in reasons) DropdownMenuItem(value: r, child: Text(r)),
          ],
          onChanged: (v) => setState(() => _reason = v ?? _reason),
        ),
      ),
      const SizedBox(height: Tk.m),
      identified(
        'return_notes_field',
        TextField(
          key: const Key('return_notes_field'),
          controller: _notes,
          maxLines: 4,
          decoration: const InputDecoration(
            labelText: 'Anything else we should know? (optional)',
            alignLabelWithHint: true,
          ),
        ),
      ),
      const SizedBox(height: Tk.m),
      identified(
        'return_resolution',
        DropdownButtonFormField<String>(
          key: const Key('return_resolution'),
          initialValue: _resolution,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'How to resolve it'),
          items: [
            for (final r in resolutions)
              DropdownMenuItem(value: r, child: Text(r)),
          ],
          onChanged: (v) => setState(() => _resolution = v ?? _resolution),
        ),
      ),
    ],
    _ => [
      Card(
        child: Padding(
          padding: const EdgeInsets.all(Tk.l),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Items', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: Tk.xs),
              Text(_picked.join(', ')),
              const SizedBox(height: Tk.m),
              Text('Reason', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: Tk.xs),
              Text(_reason),
              const SizedBox(height: Tk.m),
              Text(
                'Resolution',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: Tk.xs),
              Text(_resolution),
            ],
          ),
        ),
      ),
      const SizedBox(height: Tk.m),
      identified(
        Store.instance.k('return_confirm'),
        CheckboxListTile(
          key: Key(Store.instance.k('return_confirm')),
          value: _understood,
          onChanged: (v) => setState(() => _understood = v ?? false),
          title: const Text('I understand this starts a return request.'),
          controlAffinity: ListTileControlAffinity.leading,
        ),
      ),
    ],
  };
}

class ReturnDoneScreen extends StatelessWidget {
  const ReturnDoneScreen({required this.orderId, super.key});

  final String orderId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Return started')),
      body: PageBody(
        children: [
          const SizedBox(height: Tk.xl),
          const Icon(Icons.check_circle_outline, size: 44, color: Tk.brand),
          const SizedBox(height: Tk.l),
          Text(
            'Return request received.',
            key: const Key('return_done_headline'),
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: Tk.s),
          Text(
            'Reference RT-$orderId · we will email a prepaid label '
            'within one working day.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: Tk.xl),
          identified(
            'view_refund_status_button',
            OutlinedButton(
              key: const Key('view_refund_status_button'),
              onPressed: () => Navigator.of(context).pushReplacement(
                MaterialPageRoute(
                  builder: (_) => RefundStatusScreen(orderId: orderId),
                ),
              ),
              child: const Text('View refund status'),
            ),
          ),
          const SizedBox(height: Tk.m),
          identified(
            'return_done_close_button',
            TextButton(
              key: const Key('return_done_close_button'),
              onPressed: () => Navigator.of(context).popUntil((r) => r.isFirst),
              child: const Text('Back to my orders'),
            ),
          ),
        ],
      ),
    );
  }
}

class RefundStatusScreen extends StatelessWidget {
  const RefundStatusScreen({required this.orderId, super.key});

  final String orderId;

  @override
  Widget build(BuildContext context) {
    final order = Store.instance.orderById(orderId);
    final refunded = order.status == OrderStatus.refunded;
    return Scaffold(
      appBar: AppBar(title: const Text('Refund status')),
      body: PageBody(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  refunded ? 'Money is back with you.' : 'We are on it.',
                  key: const Key('refund_headline'),
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
              ),
              StatusPill(
                refunded ? 'Refunded' : 'In progress',
                tone: refunded ? Tone.good : Tone.warn,
              ),
            ],
          ),
          const SizedBox(height: Tk.xs),
          Text(
            'Order #${order.id} · ${money(order.totalCents)} to '
            '${order.paymentLabel}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: Tk.xl),
          Timeline(
            steps: [
              const TimelineStep(
                'Request received',
                'We logged your return request.',
                done: true,
              ),
              TimelineStep(
                'Label issued',
                'Check your email for the label.',
                done: true,
              ),
              TimelineStep(
                'Item received',
                refunded
                    ? 'Arrived at the warehouse.'
                    : 'Waiting on the parcel.',
                done: refunded,
              ),
              TimelineStep(
                'Refund issued',
                refunded
                    ? 'Sent back to your card.'
                    : 'Within 3 days of arrival.',
                done: refunded,
              ),
            ],
          ),
          identified(
            'refund_help_button',
            OutlinedButton.icon(
              key: const Key('refund_help_button'),
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Opening support…'),
                  duration: Duration(seconds: 2),
                ),
              ),
              icon: const Icon(Icons.support_agent_outlined, size: 18),
              label: const Text('Something looks wrong'),
            ),
          ),
        ],
      ),
    );
  }
}
