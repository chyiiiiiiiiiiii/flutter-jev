import 'package:flutter/material.dart';

import 'theme.dart';

/// Shared presentation pieces. Anything that appears on more than one screen
/// lives here so the screens stay about behaviour rather than padding.

/// Wraps a widget so marionette can match it by Semantics `identifier` as well
/// as by `Key`. Two stable selectors beats one, and neither is the visible copy.
Widget identified(String id, Widget child) =>
    Semantics(identifier: id, container: true, child: child);

enum Tone { neutral, good, warn, bad }

class StatusPill extends StatelessWidget {
  const StatusPill(this.label, {this.tone = Tone.neutral, super.key});

  final String label;
  final Tone tone;

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = switch (tone) {
      Tone.good => (Tk.brandSoft, Tk.brand),
      Tone.warn => (Tk.warnSoft, Tk.warn),
      Tone.bad => (Tk.dangerSoft, Tk.danger),
      Tone.neutral => (const Color(0xFFECEEF4), Tk.inkSoft),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: fg,
          fontSize: 11.5,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {this.subtitle, this.trailing, super.key});

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Tk.m),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleLarge),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(subtitle!, style: Theme.of(context).textTheme.bodySmall),
                ],
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

/// A card with a thin leading tile, used for orders, addresses and cards.
class RowCard extends StatelessWidget {
  const RowCard({
    required this.icon,
    required this.title,
    this.subtitle,
    this.meta,
    this.pill,
    this.onTap,
    this.trailing,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final String? meta;
  final Widget? pill;
  final VoidCallback? onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(Tk.radius),
        child: Padding(
          padding: const EdgeInsets.all(Tk.l),
          child: Row(
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
                child: Icon(icon, size: 20, color: Tk.brand),
              ),
              const SizedBox(width: Tk.m),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(title, style: text.titleMedium)),
                        ?pill,
                      ],
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(subtitle!, style: text.bodySmall),
                    ],
                    if (meta != null) ...[
                      const SizedBox(height: Tk.s),
                      Text(
                        meta!,
                        style: text.bodySmall?.copyWith(
                          color: Tk.ink,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (trailing != null)
                trailing!
              else if (onTap != null)
                const Padding(
                  padding: EdgeInsets.only(left: Tk.s),
                  child: Icon(Icons.chevron_right, color: Tk.inkSoft, size: 20),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A vertical progress timeline, used by tracking and refund status.
class Timeline extends StatelessWidget {
  const Timeline({required this.steps, super.key});

  final List<TimelineStep> steps;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      children: [
        for (var i = 0; i < steps.length; i++)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Column(
                children: [
                  Container(
                    width: 22,
                    height: 22,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: steps[i].done ? Tk.brand : Tk.surface,
                      border: Border.all(
                        color: steps[i].done ? Tk.brand : Tk.line,
                        width: 1.6,
                      ),
                    ),
                    child: steps[i].done
                        ? const Icon(Icons.check, size: 13, color: Colors.white)
                        : null,
                  ),
                  if (i != steps.length - 1)
                    Container(
                      width: 1.6,
                      height: 46,
                      color: steps[i + 1].done ? Tk.brand : Tk.line,
                    ),
                ],
              ),
              const SizedBox(width: Tk.m),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(bottom: Tk.xl),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        steps[i].title,
                        style: text.titleMedium?.copyWith(
                          color: steps[i].done ? Tk.ink : Tk.inkSoft,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(steps[i].detail, style: text.bodySmall),
                    ],
                  ),
                ),
              ),
            ],
          ),
      ],
    );
  }
}

class TimelineStep {
  const TimelineStep(this.title, this.detail, {this.done = false});

  final String title;
  final String detail;
  final bool done;
}

/// Empty, loading and error states. A demo that never shows these is not
/// exercising the paths that break real test suites.
class EmptyState extends StatelessWidget {
  const EmptyState({
    required this.icon,
    required this.title,
    required this.body,
    this.action,
    super.key,
  });

  final IconData icon;
  final String title;
  final String body;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(Tk.xxl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: Tk.surface,
                shape: BoxShape.circle,
                border: Border.all(color: Tk.line),
              ),
              child: Icon(icon, color: Tk.inkSoft),
            ),
            const SizedBox(height: Tk.l),
            Text(
              title,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: Tk.xs),
            Text(
              body,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (action != null) ...[const SizedBox(height: Tk.l), action!],
          ],
        ),
      ),
    );
  }
}

class LoadingList extends StatelessWidget {
  const LoadingList({this.count = 3, super.key});

  final int count;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.zero,
      children: [
        for (var i = 0; i < count; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: Tk.m),
            child: Container(
              height: 88,
              decoration: BoxDecoration(
                color: Tk.surface,
                borderRadius: BorderRadius.circular(Tk.radius),
                border: Border.all(color: Tk.line),
              ),
              child: const Center(
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Centres and constrains page content so the app reads well on a phone and
/// on a desktop window, which matters because the agent drives both.
class PageBody extends StatelessWidget {
  const PageBody({required this.children, this.padding, super.key});

  final List<Widget> children;
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: Tk.maxContent),
        child: ListView(
          padding: padding ?? const EdgeInsets.all(Tk.l),
          children: children,
        ),
      ),
    );
  }
}

class QuantityStepper extends StatelessWidget {
  const QuantityStepper({
    required this.value,
    required this.onChanged,
    required this.idPrefix,
    super.key,
  });

  final int value;
  final ValueChanged<int> onChanged;
  final String idPrefix;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: Tk.line),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          identified(
            '${idPrefix}_minus',
            IconButton(
              key: Key('${idPrefix}_minus'),
              onPressed: value > 1 ? () => onChanged(value - 1) : null,
              icon: const Icon(Icons.remove, size: 16),
              visualDensity: VisualDensity.compact,
              tooltip: 'Decrease quantity',
            ),
          ),
          Text(
            '$value',
            key: Key('${idPrefix}_value'),
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          identified(
            '${idPrefix}_plus',
            IconButton(
              key: Key('${idPrefix}_plus'),
              onPressed: value < 9 ? () => onChanged(value + 1) : null,
              icon: const Icon(Icons.add, size: 16),
              visualDensity: VisualDensity.compact,
              tooltip: 'Increase quantity',
            ),
          ),
        ],
      ),
    );
  }
}
