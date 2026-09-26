import 'package:flutter/material.dart';

import '../data.dart';
import '../kit.dart';
import '../theme.dart';

/// Browse, product detail, cart and checkout. The flow mutates `Store` so an
/// agent that adds something can be asked about it three screens later.

class ShopTab extends StatefulWidget {
  const ShopTab({super.key});

  @override
  State<ShopTab> createState() => _ShopTabState();
}

class _ShopTabState extends State<ShopTab> {
  final _search = TextEditingController();
  String _category = 'All';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<Product> get _results {
    final q = _search.text.trim().toLowerCase();
    return Store.instance.products.where((p) {
      if (_category != 'All' && p.category != _category) return false;
      if (q.isEmpty) return true;
      return p.name.toLowerCase().contains(q) ||
          p.blurb.toLowerCase().contains(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final categories = <String>[
      'All',
      ...{for (final p in Store.instance.products) p.category},
    ];
    final results = _results;

    return PageBody(
      children: [
        const SectionHeader('Shop', subtitle: 'Six things we actually use.'),
        identified(
          'shop_search',
          TextField(
            key: const Key('shop_search'),
            controller: _search,
            onChanged: (_) => setState(() {}),
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(
              hintText: 'Search the catalogue',
              prefixIcon: Icon(Icons.search, size: 19),
            ),
          ),
        ),
        const SizedBox(height: Tk.m),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final c in categories) ...[
                identified(
                  'shop_filter_${c.toLowerCase()}',
                  FilterChip(
                    key: Key('shop_filter_${c.toLowerCase()}'),
                    label: Text(c),
                    selected: _category == c,
                    showCheckmark: false,
                    selectedColor: Tk.brandSoft,
                    side: const BorderSide(color: Tk.line),
                    onSelected: (_) => setState(() => _category = c),
                  ),
                ),
                const SizedBox(width: Tk.s),
              ],
            ],
          ),
        ),
        const SizedBox(height: Tk.l),
        if (results.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: Tk.xl),
            child: EmptyState(
              key: const Key('shop_empty'),
              icon: Icons.search_off,
              title: 'Nothing matches that',
              body: 'Try a shorter word, or clear the filters.',
              action: identified(
                'shop_clear_search',
                OutlinedButton(
                  key: const Key('shop_clear_search'),
                  onPressed: () => setState(() {
                    _search.clear();
                    _category = 'All';
                  }),
                  child: const Text('Clear search'),
                ),
              ),
            ),
          )
        else
          LayoutBuilder(
            builder: (context, constraints) {
              // Two tiles side by side once there is room for them.
              final columns = constraints.maxWidth >= 440 ? 2 : 1;
              final width =
                  (constraints.maxWidth - Tk.m * (columns - 1)) / columns;
              return Wrap(
                spacing: Tk.m,
                runSpacing: Tk.m,
                children: [
                  for (final p in results)
                    SizedBox(
                      width: width,
                      child: _ProductTile(product: p),
                    ),
                ],
              );
            },
          ),
      ],
    );
  }
}

class _ProductTile extends StatelessWidget {
  const _ProductTile({required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return identified(
      'product_${product.id}',
      Card(
        key: Key('product_${product.id}'),
        child: InkWell(
          borderRadius: BorderRadius.circular(Tk.radius),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => ProductDetailScreen(product: product),
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(Tk.l),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: Tk.canvas,
                    borderRadius: BorderRadius.circular(Tk.radiusSm),
                    border: Border.all(color: Tk.line),
                  ),
                  child: Icon(product.icon, size: 20, color: Tk.brand),
                ),
                const SizedBox(height: Tk.m),
                Text(product.name, style: text.titleMedium),
                const SizedBox(height: 2),
                Text(
                  product.blurb,
                  style: text.bodySmall,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: Tk.m),
                // Wrap, not Row: the pill drops to its own line in a narrow
                // tile rather than overflowing.
                Wrap(
                  spacing: Tk.s,
                  runSpacing: Tk.xs,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      money(product.priceCents),
                      style: text.titleMedium?.copyWith(color: Tk.brand),
                    ),
                    if (!product.inStock)
                      const StatusPill('Out of stock', tone: Tone.bad),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class ProductDetailScreen extends StatefulWidget {
  const ProductDetailScreen({required this.product, super.key});

  final Product product;

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  int _qty = 1;

  /// How many were just added. Shown inline next to the buttons rather than
  /// in a SnackBar, which would sit on top of View cart and, while it is up,
  /// take the button out of the tree for anything reading it.
  int _added = 0;

  List<String> get _specs => switch (widget.product.category) {
    'Wear' => const [
      'Merino and nylon blend',
      'Machine wash cold',
      'Reinforced heel and toe',
      'One year hole guarantee',
    ],
    'Audio' => const [
      'Bluetooth 5.4, pairs two at once',
      'IP67 splash and dust rating',
      '20 minute charge for four hours play',
      'Two year repair cover',
    ],
    _ => const [
      'Lead-free, food safe',
      'Dishwasher safe',
      'Spare parts sold separately',
      'One year breakage cover',
    ],
  };

  void _add() {
    for (var i = 0; i < _qty; i++) {
      Store.instance.addToCart(widget.product.id);
    }
    setState(() => _added += _qty);
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.product;
    final text = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: Text(p.name)),
      // Buying stays in reach whatever the scroll position, and nothing
      // transient is drawn over it.
      bottomNavigationBar: SafeArea(
        child: Container(
          decoration: const BoxDecoration(
            color: Tk.surface,
            border: Border(top: BorderSide(color: Tk.line)),
          ),
          padding: const EdgeInsets.fromLTRB(Tk.l, Tk.m, Tk.l, Tk.m),
          child: Center(
            heightFactor: 1,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: Tk.maxContent),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_added > 0) ...[
                    Row(
                      key: const Key('added_to_cart_note'),
                      children: [
                        const Icon(
                          Icons.check_circle,
                          size: 18,
                          color: Tk.brand,
                        ),
                        const SizedBox(width: Tk.s),
                        Expanded(
                          child: Text(
                            '$_added in your cart',
                            style: text.bodyMedium?.copyWith(color: Tk.ink),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: Tk.s),
                  ],
                  Row(
                    children: [
                      Expanded(
                        child: identified(
                          'view_cart_button',
                          OutlinedButton(
                            key: const Key('view_cart_button'),
                            onPressed: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => const CartScreen(),
                              ),
                            ),
                            child: Text(
                              Store.instance.cartCount > 0
                                  ? 'View cart (${Store.instance.cartCount})'
                                  : 'View cart',
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: Tk.m),
                      Expanded(
                        child: identified(
                          'add_to_cart_button',
                          FilledButton(
                            key: const Key('add_to_cart_button'),
                            onPressed: p.inStock ? _add : null,
                            child: Text(
                              p.inStock ? 'Add to cart' : 'Out of stock',
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      body: SafeArea(
        child: PageBody(
          children: [
            Container(
              height: 160,
              decoration: BoxDecoration(
                color: Tk.surface,
                borderRadius: BorderRadius.circular(Tk.radius),
                border: Border.all(color: Tk.line),
              ),
              child: Icon(p.icon, size: 56, color: Tk.brand),
            ),
            const SizedBox(height: Tk.l),
            Text(p.name, style: text.headlineSmall),
            const SizedBox(height: Tk.s),
            Row(
              children: [
                StatusPill(p.category),
                const SizedBox(width: Tk.s),
                if (!p.inStock)
                  const StatusPill('Out of stock', tone: Tone.bad),
              ],
            ),
            const SizedBox(height: Tk.m),
            Text(money(p.priceCents), style: text.headlineSmall),
            const SizedBox(height: Tk.m),
            Text(p.blurb, style: text.bodyMedium),
            const SizedBox(height: Tk.l),
            const Divider(),
            const SizedBox(height: Tk.l),
            Text('Specification', style: text.titleMedium),
            const SizedBox(height: Tk.s),
            for (final line in _specs)
              Padding(
                padding: const EdgeInsets.only(bottom: Tk.xs),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 6, right: Tk.s),
                      child: Icon(Icons.circle, size: 5, color: Tk.inkSoft),
                    ),
                    Expanded(child: Text(line, style: text.bodyMedium)),
                  ],
                ),
              ),
            const SizedBox(height: Tk.l),
            Row(
              children: [
                Text('Quantity', style: text.titleMedium),
                const Spacer(),
                QuantityStepper(
                  value: _qty,
                  onChanged: (v) => setState(() => _qty = v),
                  idPrefix: 'product_qty',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class CartScreen extends StatelessWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final store = Store.instance;
    return Scaffold(
      appBar: AppBar(title: const Text('Cart')),
      body: SafeArea(
        child: ListenableBuilder(
          listenable: store,
          builder: (context, _) {
            if (store.cart.isEmpty) {
              return EmptyState(
                key: const Key('cart_empty'),
                icon: Icons.shopping_cart_outlined,
                title: 'Your cart is empty',
                body: 'Everything you add here stays until you check out.',
                action: identified(
                  'cart_browse_button',
                  FilledButton(
                    key: const Key('cart_browse_button'),
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Browse the shop'),
                  ),
                ),
              );
            }

            final lines = store.cart.entries
                .map(
                  (e) => (
                    product: store.products.firstWhere((p) => p.id == e.key),
                    qty: e.value,
                  ),
                )
                .toList();
            final subtotal = store.cartTotalCents;
            final shipping = subtotal > 10000 ? 0 : 590;

            return PageBody(
              children: [
                SectionHeader(
                  '${store.cartCount} item${store.cartCount == 1 ? '' : 's'}',
                  subtitle: 'Prices include tax.',
                ),
                for (final line in lines) ...[
                  _CartLine(product: line.product, qty: line.qty),
                  const SizedBox(height: Tk.m),
                ],
                const SizedBox(height: Tk.s),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(Tk.l),
                    child: Column(
                      children: [
                        _SummaryRow('Subtotal', money(subtotal)),
                        const SizedBox(height: Tk.s),
                        _SummaryRow(
                          'Shipping',
                          shipping == 0 ? 'Free' : money(shipping),
                        ),
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: Tk.m),
                          child: Divider(),
                        ),
                        _SummaryRow(
                          'Total',
                          money(subtotal + shipping),
                          strong: true,
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: Tk.l),
                identified(
                  'checkout_button',
                  FilledButton(
                    key: const Key('checkout_button'),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const CheckoutScreen()),
                    ),
                    child: const Text('Checkout'),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _CartLine extends StatelessWidget {
  const _CartLine({required this.product, required this.qty});

  final Product product;
  final int qty;

  @override
  Widget build(BuildContext context) {
    final store = Store.instance;
    return RowCard(
      key: Key('cart_line_${product.id}'),
      icon: product.icon,
      title: product.name,
      subtitle: money(product.priceCents),
      trailing: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          identified(
            'cart_remove_${product.id}',
            IconButton(
              key: Key('cart_remove_${product.id}'),
              onPressed: () => store.setCartQty(product.id, 0),
              icon: const Icon(Icons.close, size: 18),
              visualDensity: VisualDensity.compact,
              tooltip: 'Remove from cart',
            ),
          ),
          const SizedBox(height: Tk.xs),
          QuantityStepper(
            value: qty,
            onChanged: (v) => store.setCartQty(product.id, v),
            idPrefix: 'cart_qty_${product.id}',
          ),
        ],
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow(this.label, this.value, {this.strong = false});

  final String label;
  final String value;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Row(
      children: [
        Text(label, style: strong ? text.titleMedium : text.bodyMedium),
        const Spacer(),
        Text(
          value,
          style: strong
              ? text.titleMedium
              : text.bodyMedium?.copyWith(color: Tk.ink),
        ),
      ],
    );
  }
}

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  String _speed = 'standard';
  bool _terms = false;
  bool _placing = false;

  Future<void> _placeOrder() async {
    setState(() => _placing = true);
    await Future<void>.delayed(Store.instance.latency);
    if (!mounted) return;
    Store.instance.clearCart();
    await Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const OrderPlacedScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final store = Store.instance;
    final address = store.addresses.first;
    final payment = store.payments.first;

    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: SafeArea(
        child: PageBody(
          children: [
            const SectionHeader('Review', subtitle: 'One last look.'),
            RowCard(
              key: const Key('checkout_address'),
              icon: Icons.home_outlined,
              title: address.label,
              subtitle: address.lines.replaceAll('\n', ', '),
            ),
            const SizedBox(height: Tk.m),
            RowCard(
              key: const Key('checkout_payment'),
              icon: payment.icon,
              title: payment.label,
              subtitle: payment.detail,
            ),
            const SizedBox(height: Tk.l),
            Text('Delivery', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: Tk.xs),
            RadioGroup<String>(
              groupValue: _speed,
              onChanged: (v) => setState(() => _speed = v ?? 'standard'),
              child: Column(
                children: [
                  identified(
                    'ship_standard',
                    const RadioListTile<String>(
                      key: Key('ship_standard'),
                      value: 'standard',
                      title: Text('Standard · 3-5 days'),
                      subtitle: Text('Free over \$100, otherwise \$5.90'),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                  identified(
                    'ship_express',
                    const RadioListTile<String>(
                      key: Key('ship_express'),
                      value: 'express',
                      title: Text('Express · next working day'),
                      subtitle: Text('\$9.90'),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: Tk.s),
            identified(
              'checkout_terms',
              CheckboxListTile(
                key: const Key('checkout_terms'),
                value: _terms,
                onChanged: (v) => setState(() => _terms = v ?? false),
                title: const Text('I agree to the returns and refund terms'),
                controlAffinity: ListTileControlAffinity.leading,
                contentPadding: EdgeInsets.zero,
                dense: true,
              ),
            ),
            const SizedBox(height: Tk.l),
            identified(
              'place_order_button',
              FilledButton(
                key: const Key('place_order_button'),
                onPressed: _terms && !_placing ? _placeOrder : null,
                child: _placing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Place order'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class OrderPlacedScreen extends StatelessWidget {
  const OrderPlacedScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: Tk.maxContent),
            child: Padding(
              padding: const EdgeInsets.all(Tk.xl),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.check_circle, size: 48, color: Tk.brand),
                  const SizedBox(height: Tk.l),
                  Text(
                    'Order placed',
                    key: const Key('order_placed_headline'),
                    textAlign: TextAlign.center,
                    style: text.headlineSmall,
                  ),
                  const SizedBox(height: Tk.s),
                  Text(
                    'A confirmation is on its way to your inbox.',
                    textAlign: TextAlign.center,
                    style: text.bodyMedium,
                  ),
                  const SizedBox(height: Tk.xl),
                  identified(
                    'back_to_shop_button',
                    FilledButton(
                      key: const Key('back_to_shop_button'),
                      onPressed: () =>
                          Navigator.of(context)
                              .popUntil((route) => route.isFirst),
                      child: const Text('Back to shop'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
