import 'package:flutter/material.dart';

import '../data.dart';
import '../kit.dart';
import '../theme.dart';

class _Faq {
  const _Faq(this.id, this.question, this.answer);

  final String id;
  final String question;
  final String answer;
}

const _faqs = [
  _Faq(
    'faq_1',
    'Where is my order right now?',
    'Open the Orders tab, choose the order and tap Track. Carrier scans '
        'usually appear within a few hours of dispatch.',
  ),
  _Faq(
    'faq_2',
    'How long do I have to return something?',
    'Thirty days from the delivery date. Anything worn or washed can only be '
        'returned if it arrived faulty.',
  ),
  _Faq(
    'faq_3',
    'When does a refund reach my account?',
    'We refund the original payment method once the parcel is scanned at our '
        'warehouse, then your bank takes three to five working days.',
  ),
  _Faq(
    'faq_4',
    'Can I change the delivery address after ordering?',
    'Only while the order is still processing. After it ships you can ask the '
        'carrier to redirect it using the tracking number.',
  ),
  _Faq(
    'faq_5',
    'What does shipping cost?',
    'Standard shipping is \$5.90 and free on orders over \$100. Everything '
        'ships from Taichung and arrives in two to four working days.',
  ),
  _Faq(
    'faq_6',
    'My parcel says delivered but I do not have it.',
    'Check with neighbours and the building lobby first, then contact us '
        'within seven days and we will open a carrier investigation.',
  ),
];

class SupportTab extends StatefulWidget {
  const SupportTab({super.key});

  @override
  State<SupportTab> createState() => _SupportTabState();
}

class _SupportTabState extends State<SupportTab> {
  final _search = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<_Faq> get _matches {
    final q = _query.trim().toLowerCase();
    if (q.isEmpty) return _faqs;
    return _faqs
        .where(
          (f) =>
              f.question.toLowerCase().contains(q) ||
              f.answer.toLowerCase().contains(q),
        )
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final matches = _matches;
    return PageBody(
      children: [
        const SectionHeader(
          'How can we help?',
          subtitle: 'Search the common questions, or talk to a person.',
        ),
        identified(
          'support_search',
          TextField(
            key: const Key('support_search'),
            controller: _search,
            onChanged: (v) => setState(() => _query = v),
            decoration: const InputDecoration(
              hintText: 'Search help',
              prefixIcon: Icon(Icons.search, size: 19),
            ),
          ),
        ),
        const SizedBox(height: Tk.l),
        if (matches.isEmpty)
          EmptyState(
            key: const Key('support_empty'),
            icon: Icons.help_outline,
            title: 'Nothing matches "${_query.trim()}"',
            body:
                'Try a shorter phrase, or contact us and describe it in your '
                'own words.',
            action: identified(
              'contact_us_button',
              FilledButton(
                key: const Key('contact_us_button'),
                onPressed: () => _openContact(context),
                child: const Text('Contact us'),
              ),
            ),
          )
        else ...[
          for (final faq in matches) ...[
            identified(
              faq.id,
              Card(
                child: Theme(
                  // ExpansionTile draws its own divider lines otherwise, which
                  // fights the card border.
                  data: Theme.of(context)
                      .copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    key: Key(faq.id),
                    title: Text(
                      faq.question,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    childrenPadding: const EdgeInsets.fromLTRB(
                      Tk.l,
                      0,
                      Tk.l,
                      Tk.l,
                    ),
                    expandedCrossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        faq.answer,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: Tk.m),
          ],
          const SizedBox(height: Tk.s),
          identified(
            'contact_us_button',
            FilledButton(
              key: const Key('contact_us_button'),
              onPressed: () => _openContact(context),
              child: const Text('Contact us'),
            ),
          ),
        ],
      ],
    );
  }

  void _openContact(BuildContext context) {
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => const ContactScreen()));
  }
}

class ContactScreen extends StatefulWidget {
  const ContactScreen({super.key});

  @override
  State<ContactScreen> createState() => _ContactScreenState();
}

class _ContactScreenState extends State<ContactScreen> {
  static const _topics = [
    'Order issue',
    'Return or refund',
    'Delivery delay',
    'Something else',
  ];

  final _order = TextEditingController();
  final _message = TextEditingController();
  String _topic = _topics.first;
  bool _attach = false;
  bool _sending = false;

  @override
  void dispose() {
    _order.dispose();
    _message.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() => _sending = true);
    await Future<void>.delayed(Store.instance.latency);
    if (!mounted) return;
    final ticket = 'CS-${DateTime.now().millisecondsSinceEpoch % 100000}';
    Store.instance.recordTicket(ticket, _order.text, _message.text);
    await Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => ContactSentScreen(ticket: ticket)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canSend = _message.text.trim().isNotEmpty && !_sending;
    return Scaffold(
      appBar: AppBar(title: const Text('Contact us')),
      body: PageBody(
        children: [
          const SectionHeader(
            'Tell us what happened',
            subtitle: 'We reply by email, usually within one working day.',
          ),
          identified(
            'contact_topic',
            DropdownButtonFormField<String>(
              isExpanded: true,
              key: const Key('contact_topic'),
              initialValue: _topic,
              decoration: const InputDecoration(labelText: 'Topic'),
              items: [
                for (final topic in _topics)
                  DropdownMenuItem(value: topic, child: Text(topic)),
              ],
              onChanged: (v) => setState(() => _topic = v ?? _topics.first),
            ),
          ),
          const SizedBox(height: Tk.m),
          identified(
            'contact_order_field',
            TextField(
              key: const Key('contact_order_field'),
              controller: _order,
              decoration: const InputDecoration(
                labelText: 'Order number (optional)',
                hintText: '5213',
              ),
            ),
          ),
          const SizedBox(height: Tk.m),
          identified(
            'contact_message_field',
            TextField(
              key: const Key('contact_message_field'),
              controller: _message,
              maxLines: 5,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(labelText: 'Message'),
            ),
          ),
          const SizedBox(height: Tk.s),
          identified(
            'contact_attach',
            CheckboxListTile(
              key: const Key('contact_attach'),
              value: _attach,
              onChanged: (v) => setState(() => _attach = v ?? false),
              title: const Text('Attach a screenshot'),
              controlAffinity: ListTileControlAffinity.leading,
              contentPadding: EdgeInsets.zero,
              dense: true,
            ),
          ),
          const SizedBox(height: Tk.l),
          identified(
            'contact_send_button',
            FilledButton(
              key: const Key('contact_send_button'),
              onPressed: canSend ? _send : null,
              child: _sending
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Send message'),
            ),
          ),
        ],
      ),
    );
  }
}

class ContactSentScreen extends StatelessWidget {
  const ContactSentScreen({required this.ticket, super.key});

  final String ticket;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Message sent')),
      body: PageBody(
        padding: const EdgeInsets.fromLTRB(Tk.l, Tk.xxl, Tk.l, Tk.l),
        children: [
          const Icon(Icons.mark_email_read_outlined, size: 34, color: Tk.brand),
          const SizedBox(height: Tk.l),
          Text(
            'Thanks, we have it.',
            key: const Key('contact_sent_headline'),
            style: text.headlineSmall,
          ),
          const SizedBox(height: Tk.s),
          Text(
            'A support agent will reply to ${Store.instance.email.isEmpty ? 'the address on your account' : Store.instance.email}.',
            style: text.bodyMedium,
          ),
          const SizedBox(height: Tk.xl),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(Tk.l),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Ticket reference', style: text.bodySmall),
                        const SizedBox(height: 2),
                        Text(
                          ticket,
                          key: const Key('contact_ticket'),
                          style: text.titleMedium,
                        ),
                      ],
                    ),
                  ),
                  const StatusPill('Open', tone: Tone.warn),
                ],
              ),
            ),
          ),
          const SizedBox(height: Tk.xl),
          identified(
            'back_to_support_button',
            OutlinedButton(
              key: const Key('back_to_support_button'),
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Back to support'),
            ),
          ),
        ],
      ),
    );
  }
}
