import 'dart:math';

import 'package:flutter/material.dart';

/// In-memory domain data and state. The store mutates so an agent's actions
/// have consequences a later assertion can actually check.

enum OrderStatus {
  processing,
  inTransit,
  delivered,
  cancelled,
  returning,
  refunded,
}

extension OrderStatusX on OrderStatus {
  String get label => switch (this) {
    OrderStatus.processing => 'Processing',
    OrderStatus.inTransit => 'In transit',
    OrderStatus.delivered => 'Delivered',
    OrderStatus.cancelled => 'Cancelled',
    OrderStatus.returning => 'Return in progress',
    OrderStatus.refunded => 'Refunded',
  };

  bool get returnable => this == OrderStatus.delivered;
  bool get cancellable => this == OrderStatus.processing;
}

class LineItem {
  const LineItem({
    required this.name,
    required this.variant,
    required this.priceCents,
    required this.qty,
    required this.icon,
  });

  final String name;
  final String variant;
  final int priceCents;
  final int qty;
  final IconData icon;

  int get totalCents => priceCents * qty;
}

class Order {
  Order({
    required this.id,
    required this.placed,
    required this.items,
    required this.status,
    required this.address,
    required this.paymentLabel,
    this.deliveredDaysAgo,
    this.carrier = 'Harbor Post',
    this.trackingNo,
  });

  final String id;
  final String placed;
  final List<LineItem> items;
  OrderStatus status;
  final String address;
  final String paymentLabel;
  final int? deliveredDaysAgo;
  final String carrier;
  final String? trackingNo;

  int get subtotalCents => items.fold(0, (sum, i) => sum + i.totalCents);
  int get shippingCents => subtotalCents > 10000 ? 0 : 590;
  int get totalCents => subtotalCents + shippingCents;
  String get title => items.length == 1
      ? items.first.name
      : '${items.first.name} + ${items.length - 1} more';
}

class Product {
  const Product({
    required this.id,
    required this.name,
    required this.blurb,
    required this.priceCents,
    required this.icon,
    required this.category,
    this.inStock = true,
  });

  final String id;
  final String name;
  final String blurb;
  final int priceCents;
  final IconData icon;
  final String category;
  final bool inStock;
}

class Address {
  const Address({
    required this.id,
    required this.label,
    required this.lines,
    this.isDefault = false,
  });

  final String id;
  final String label;
  final String lines;
  final bool isDefault;
}

class PaymentMethod {
  const PaymentMethod({
    required this.id,
    required this.label,
    required this.detail,
    required this.icon,
    this.isDefault = false,
  });

  final String id;
  final String label;
  final String detail;
  final IconData icon;
  final bool isDefault;
}

String money(int cents) => '\$${(cents / 100).toStringAsFixed(2)}';

/// The single mutable store. `ChangeNotifier` keeps it obvious which screens
/// rebuild when an action lands.
class Store extends ChangeNotifier {
  Store._();
  static final Store instance = Store._();

  bool signedIn = false;
  String email = '';

  /// Toggled from Settings so the agent can be pointed at the failure paths.
  bool simulateSlowNetwork = false;
  bool simulateOrdersError = false;

  /// Shuffles the things a hand-written test depends on.
  ///
  /// Real apps churn: someone renames a key, reorders a list, adds a
  /// confirmation step. A script encodes those choices and breaks; an agent
  /// reads whatever is on screen and carries on. With a seed this is
  /// reproducible, so the same drift can be replayed for both modes.
  int chaosSeed = 0;

  bool get chaos => chaosSeed != 0;

  /// Set the churn and rebuild. Callers outside the store cannot invoke
  /// `notifyListeners` themselves, so the store owns this.
  void setChaos(int seed) {
    chaosSeed = seed;
    notifyListeners();
  }

  Random get _rng => Random(chaosSeed);

  /// Suffix appended to a renamed widget key, standing in for a developer
  /// having renamed it since the test was written.
  String get keySuffix => chaos ? '_v${chaosSeed % 90 + 10}' : '';

  /// Renames roughly two keys in five, chosen deterministically from the seed.
  ///
  /// Renaming everything would be less true and less useful: a real week
  /// touches some widgets and not others, so each seed breaks a hand-written
  /// test at a different step. Renaming all of them just breaks it at step one,
  /// every time.
  bool renamed(String base) {
    if (!chaos) return false;
    // XOR-ing a stable hashCode with the seed barely moved the low bits, so
    // every seed picked the same widgets. Hashing the pair together does.
    var h = 0x811c9dc5;
    for (final unit in '$base#$chaosSeed'.codeUnits) {
      h = ((h ^ unit) * 0x01000193) & 0x7fffffff;
    }
    return h % 5 < 2;
  }

  String k(String base) => renamed(base) ? '$base$keySuffix' : base;

  /// Labels a script might have matched on by text.
  String label(String base) {
    if (!chaos) return base;
    const swaps = {
      'Sign in': 'Log in',
      'Start a return': 'Return this item',
      'Continue': 'Next step',
      'Submit return request': 'Send the request',
      'Contact us': 'Talk to a person',
      'Add to cart': 'Put in basket',
      'Add an address': 'New address',
      'Save address': 'Store address',
    };
    return swaps[base] ?? base;
  }

  /// Does the return flow demand an extra acknowledgement this run?
  bool get extraConfirmStep => chaos && _rng.nextBool();

  bool emailUpdates = true;
  bool pushUpdates = false;
  bool returnReminders = true;

  final Map<String, int> cart = {};

  /// Support requests sent this session, so a runner can check what actually
  /// reached the store rather than trusting the agent's own verdict.
  final List<Map<String, String>> tickets = [];

  void recordTicket(String id, String orderId, String message) {
    tickets.add({'id': id, 'order': orderId, 'message': message});
    notifyListeners();
  }

  List<Order> orders = _seedOrders();

  static List<Order> _seedOrders() => [
    Order(
      id: '5207',
      placed: '12 Sep 2026',
      status: OrderStatus.delivered,
      deliveredDaysAgo: 8,
      trackingNo: 'HP-7302-118',
      address: 'Home · 27 Harbor Ln, Taichung',
      paymentLabel: 'Visa ·· 4242',
      items: const [
        LineItem(
          name: 'Pour-over kit',
          variant: 'Matte white / 600ml',
          priceCents: 5800,
          qty: 1,
          icon: Icons.coffee_maker_outlined,
        ),
      ],
    ),
    Order(
      id: '5213',
      placed: '18 Sep 2026',
      status: OrderStatus.inTransit,
      trackingNo: 'HP-7302-124',
      address: 'Home · 27 Harbor Ln, Taichung',
      paymentLabel: 'Visa ·· 4242',
      items: const [
        LineItem(
          name: 'Pocket speaker',
          variant: 'Cobalt / Bluetooth',
          priceCents: 9900,
          qty: 1,
          icon: Icons.speaker_outlined,
        ),
        LineItem(
          name: 'USB-C cable',
          variant: '1 m',
          priceCents: 900,
          qty: 2,
          icon: Icons.cable_outlined,
        ),
      ],
    ),
    Order(
      id: '5198',
      placed: '02 Sep 2026',
      status: OrderStatus.delivered,
      deliveredDaysAgo: 19,
      trackingNo: 'HP-7301-977',
      address: 'Workshop · 3F, 51 Dadun Rd, Taichung',
      paymentLabel: 'Apple Pay',
      items: const [
        LineItem(
          name: 'Glass carafe',
          variant: 'Clear / 1L',
          priceCents: 3600,
          qty: 1,
          icon: Icons.local_drink_outlined,
        ),
      ],
    ),
    Order(
      id: '5191',
      placed: '27 Aug 2026',
      status: OrderStatus.refunded,
      address: 'Home · 27 Harbor Ln, Taichung',
      paymentLabel: 'Visa ·· 4242',
      items: const [
        LineItem(
          name: 'Enamel plate',
          variant: 'Speckled',
          priceCents: 1800,
          qty: 4,
          icon: Icons.dinner_dining_outlined,
        ),
      ],
    ),
    Order(
      id: '5184',
      placed: '21 Aug 2026',
      status: OrderStatus.cancelled,
      address: 'Home · 27 Harbor Ln, Taichung',
      paymentLabel: 'Visa ·· 4242',
      items: const [
        LineItem(
          name: 'Clip-on reading light',
          variant: 'Graphite',
          priceCents: 4200,
          qty: 1,
          icon: Icons.light_outlined,
        ),
      ],
    ),
    Order(
      id: '5226',
      placed: '20 Sep 2026',
      status: OrderStatus.processing,
      address: 'Home · 27 Harbor Ln, Taichung',
      paymentLabel: 'Visa ·· 4242',
      items: const [
        LineItem(
          name: 'Merino socks',
          variant: 'Grey / M',
          priceCents: 2200,
          qty: 3,
          icon: Icons.checkroom_outlined,
        ),
      ],
    ),
  ];

  final List<Product> products = const [
    Product(
      id: 'p-pourover',
      name: 'Pour-over kit',
      blurb: 'Dripper, carafe and filters, 600ml.',
      priceCents: 5800,
      icon: Icons.coffee_maker_outlined,
      category: 'Kitchen',
    ),
    Product(
      id: 'p-carafe',
      name: 'Glass carafe',
      blurb: 'Borosilicate, one litre, fridge door size.',
      priceCents: 3600,
      icon: Icons.local_drink_outlined,
      category: 'Kitchen',
    ),
    Product(
      id: 'p-speaker',
      name: 'Pocket speaker',
      blurb: 'Bluetooth, 12 hour battery, splash-proof.',
      priceCents: 9900,
      icon: Icons.speaker_outlined,
      category: 'Audio',
    ),
    Product(
      id: 'p-radio',
      name: 'Travel radio',
      blurb: 'FM and DAB, charges over USB-C.',
      priceCents: 6900,
      icon: Icons.radio_outlined,
      category: 'Audio',
      inStock: false,
    ),
    Product(
      id: 'p-socks',
      name: 'Merino socks',
      blurb: 'Three pairs, cushioned sole.',
      priceCents: 2200,
      icon: Icons.checkroom_outlined,
      category: 'Wear',
    ),
    Product(
      id: 'p-plate',
      name: 'Enamel plate',
      blurb: 'Speckled steel enamel, oven safe.',
      priceCents: 1800,
      icon: Icons.dinner_dining_outlined,
      category: 'Kitchen',
    ),
  ];

  // Growable, because a Save button that shows a confirmation without
  // persisting anything is exactly the defect these flows exist to catch.
  final List<Address> addresses = _seedAddresses();

  static List<Address> _seedAddresses() => [
    const Address(
      id: 'addr_home',
      label: 'Home',
      lines: '27 Harbor Ln\nXitun District, Taichung 407',
      isDefault: true,
    ),
    const Address(
      id: 'addr_workshop',
      label: 'Workshop',
      lines: '3F, 51 Dadun Rd\nNantun District, Taichung 408',
    ),
  ];

  final List<PaymentMethod> payments = _seedPayments();

  static List<PaymentMethod> _seedPayments() => [
    const PaymentMethod(
      id: 'pay_visa',
      label: 'Visa ·· 4242',
      detail: 'Expires 09/29',
      icon: Icons.credit_card,
      isDefault: true,
    ),
    const PaymentMethod(
      id: 'pay_apple',
      label: 'Apple Pay',
      detail: 'Default device wallet',
      icon: Icons.account_balance_wallet_outlined,
    ),
  ];

  Order orderById(String id) => orders.firstWhere((o) => o.id == id);

  /// The store is a singleton, so every test has to be able to put it back.
  void reset() {
    orders = _seedOrders();
    addresses
      ..clear()
      ..addAll(_seedAddresses());
    payments
      ..clear()
      ..addAll(_seedPayments());
    cart.clear();
    tickets.clear();
    signedIn = false;
    email = '';
    simulateSlowNetwork = false;
    simulateOrdersError = false;
    // chaosSeed is deliberately preserved: it is set per run, not per reset.
    emailUpdates = true;
    pushUpdates = false;
    returnReminders = true;
    notifyListeners();
  }

  Duration get latency =>
      Duration(milliseconds: simulateSlowNetwork ? 2200 : 260);

  int get cartCount => cart.values.fold(0, (a, b) => a + b);

  int get cartTotalCents => cart.entries.fold(0, (sum, e) {
    final p = products.firstWhere((p) => p.id == e.key);
    return sum + p.priceCents * e.value;
  });

  void signIn(String address) {
    signedIn = true;
    email = address;
    notifyListeners();
  }

  void addToCart(String productId) {
    cart.update(productId, (v) => v + 1, ifAbsent: () => 1);
    notifyListeners();
  }

  void setCartQty(String productId, int qty) {
    if (qty <= 0) {
      cart.remove(productId);
    } else {
      cart[productId] = qty;
    }
    notifyListeners();
  }

  void clearCart() {
    cart.clear();
    notifyListeners();
  }

  void startReturn(String orderId) {
    orderById(orderId).status = OrderStatus.returning;
    notifyListeners();
  }

  void cancelOrder(String orderId) {
    orderById(orderId).status = OrderStatus.cancelled;
    notifyListeners();
  }

  void addAddress(String label, String lines, {bool makeDefault = false}) {
    final id =
        'addr_${label.toLowerCase().replaceAll(RegExp('[^a-z0-9]+'), '_')}';
    addresses.add(Address(id: id, label: label, lines: lines));
    if (makeDefault) setDefaultAddress(id);
    notifyListeners();
  }

  void updateAddress(
    String id,
    String label,
    String lines, {
    bool makeDefault = false,
  }) {
    final at = addresses.indexWhere((a) => a.id == id);
    if (at < 0) return;
    addresses[at] = Address(
      id: id,
      label: label,
      lines: lines,
      isDefault: addresses[at].isDefault,
    );
    if (makeDefault) setDefaultAddress(id);
    notifyListeners();
  }

  void setDefaultAddress(String id) {
    for (var i = 0; i < addresses.length; i++) {
      final a = addresses[i];
      addresses[i] = Address(
        id: a.id,
        label: a.label,
        lines: a.lines,
        isDefault: a.id == id,
      );
    }
    notifyListeners();
  }

  void addPayment(String label, String detail) {
    payments.add(
      PaymentMethod(
        id: 'pay_${payments.length + 1}',
        label: label,
        detail: detail,
        icon: Icons.credit_card,
      ),
    );
    notifyListeners();
  }

  void toggle(String which, bool value) {
    switch (which) {
      case 'email':
        emailUpdates = value;
      case 'push':
        pushUpdates = value;
      case 'returns':
        returnReminders = value;
      case 'slow':
        simulateSlowNetwork = value;
      case 'error':
        simulateOrdersError = value;
    }
    notifyListeners();
  }
}
