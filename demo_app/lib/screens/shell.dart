import 'package:flutter/material.dart';

import '../data.dart';
import '../kit.dart';
import '../theme.dart';
import 'account.dart';
import 'orders.dart';
import 'shop.dart';
import 'support.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;

  static const _titles = ['Boxtide', 'Orders', 'Shop', 'Support', 'Account'];

  void _goTo(int tab) => setState(() => _tab = tab);

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Store.instance,
      builder: (context, _) {
        final pages = [
          HomeTab(onJump: _goTo),
          const OrdersTab(),
          const ShopTab(),
          const SupportTab(),
          const ProfileTab(),
        ];
        return Scaffold(
          appBar: AppBar(
            title: Text(_titles[_tab]),
            actions: [
              identified(
                'cart_button',
                IconButton(
                  key: const Key('cart_button'),
                  tooltip: 'Cart',
                  onPressed: () => Navigator.of(
                    context,
                  ).push(MaterialPageRoute(builder: (_) => const CartScreen())),
                  icon: Badge(
                    isLabelVisible: Store.instance.cartCount > 0,
                    label: Text('${Store.instance.cartCount}'),
                    child: const Icon(Icons.shopping_bag_outlined),
                  ),
                ),
              ),
              const SizedBox(width: Tk.xs),
            ],
          ),
          body: pages[_tab],
          bottomNavigationBar: NavigationBar(
            key: const Key('bottom_nav'),
            selectedIndex: _tab,
            onDestinationSelected: _goTo,
            destinations: [
              const NavigationDestination(
                key: Key('nav_home'),
                icon: Icon(Icons.home_outlined),
                selectedIcon: Icon(Icons.home),
                label: 'Home',
              ),
              NavigationDestination(
                key: Key(Store.instance.k('nav_orders')),
                icon: Icon(Icons.receipt_long_outlined),
                selectedIcon: Icon(Icons.receipt_long),
                label: 'Orders',
              ),
              const NavigationDestination(
                key: Key('nav_shop'),
                icon: Icon(Icons.storefront_outlined),
                selectedIcon: Icon(Icons.storefront),
                label: 'Shop',
              ),
              const NavigationDestination(
                key: Key('nav_support'),
                icon: Icon(Icons.support_agent_outlined),
                selectedIcon: Icon(Icons.support_agent),
                label: 'Support',
              ),
              const NavigationDestination(
                key: Key('nav_account'),
                icon: Icon(Icons.person_outline),
                selectedIcon: Icon(Icons.person),
                label: 'Account',
              ),
            ],
          ),
        );
      },
    );
  }
}

class HomeTab extends StatelessWidget {
  const HomeTab({required this.onJump, super.key});

  /// Lets the hero cards move the user to another tab rather than pushing a
  /// duplicate route, which keeps the back stack honest for the agent.
  final void Function(int tab) onJump;

  @override
  Widget build(BuildContext context) {
    final store = Store.instance;
    final text = Theme.of(context).textTheme;
    final active = store.orders
        .where(
          (o) =>
              o.status == OrderStatus.inTransit ||
              o.status == OrderStatus.processing,
        )
        .toList();
    final returning = store.orders
        .where((o) => o.status == OrderStatus.returning)
        .toList();

    return PageBody(
      padding: const EdgeInsets.fromLTRB(Tk.l, Tk.l, Tk.l, Tk.xxl),
      children: [
        Container(
          padding: const EdgeInsets.all(Tk.l),
          decoration: BoxDecoration(
            color: Tk.ink,
            borderRadius: BorderRadius.circular(Tk.radius),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      store.email.isEmpty ? 'Demo account' : store.email,
                      style: text.bodySmall?.copyWith(color: Tk.brandSoft),
                    ),
                    const SizedBox(height: Tk.xs),
                    Text(
                      active.isEmpty
                          ? 'Nothing on the way'
                          : '${active.length} parcel${active.length == 1 ? '' : 's'} on the way',
                      style: text.titleLarge?.copyWith(color: Colors.white),
                    ),
                  ],
                ),
              ),
              Text(
                '${store.orders.length}',
                style: text.headlineMedium?.copyWith(color: Tk.warn),
              ),
              const SizedBox(width: Tk.xs),
              Text(
                'orders',
                style: text.bodySmall?.copyWith(color: Tk.brandSoft),
              ),
            ],
          ),
        ),
        const SizedBox(height: Tk.xl),
        if (active.isNotEmpty) ...[
          const SectionHeader(
            'Tracking',
            subtitle: 'Parcels that have not reached you yet.',
          ),
          for (final order in active)
            Padding(
              padding: const EdgeInsets.only(bottom: Tk.m),
              child: identified(
                'home_active_${order.id}',
                RowCard(
                  key: Key('home_active_${order.id}'),
                  icon: Icons.local_shipping_outlined,
                  title: order.title,
                  subtitle: 'Order #${order.id} · ${order.carrier}',
                  pill: StatusPill(order.status.label, tone: Tone.warn),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => TrackingScreen(orderId: order.id),
                    ),
                  ),
                ),
              ),
            ),
          const SizedBox(height: Tk.l),
        ],
        if (returning.isNotEmpty) ...[
          const SectionHeader('Returns'),
          for (final order in returning)
            Padding(
              padding: const EdgeInsets.only(bottom: Tk.m),
              child: identified(
                'home_return_${order.id}',
                RowCard(
                  key: Key('home_return_${order.id}'),
                  icon: Icons.assignment_return_outlined,
                  title: order.title,
                  subtitle: 'Order #${order.id}',
                  pill: const StatusPill('In progress', tone: Tone.neutral),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => RefundStatusScreen(orderId: order.id),
                    ),
                  ),
                ),
              ),
            ),
          const SizedBox(height: Tk.l),
        ],
        const SectionHeader('Shortcuts'),
        _Tile(
          id: 'home_go_orders',
          icon: Icons.receipt_long_outlined,
          title: 'Your orders',
          body: 'Track, send back or cancel a purchase.',
          onTap: () => onJump(1),
        ),
        const SizedBox(height: Tk.m),
        _Tile(
          id: 'home_go_shop',
          icon: Icons.storefront_outlined,
          title: 'Shop',
          body: 'Kitchen, audio and everyday wear.',
          onTap: () => onJump(2),
        ),
        const SizedBox(height: Tk.m),
        _Tile(
          id: 'home_go_support',
          icon: Icons.support_agent_outlined,
          title: 'Help centre',
          body: 'Common questions, or write to the team.',
          onTap: () => onJump(3),
        ),
        const SizedBox(height: Tk.xl),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(Tk.l),
            child: Row(
              children: [
                const Icon(Icons.local_shipping_outlined, color: Tk.warn),
                const SizedBox(width: Tk.m),
                Expanded(
                  child: Text(
                    'Shipping is free above \$100, and returns stay open for 30 days.',
                    style: text.bodySmall,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({
    required this.id,
    required this.icon,
    required this.title,
    required this.body,
    required this.onTap,
  });

  final String id;
  final IconData icon;
  final String title;
  final String body;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return identified(
      id,
      RowCard(
        key: Key(id),
        icon: icon,
        title: title,
        subtitle: body,
        onTap: onTap,
      ),
    );
  }
}
