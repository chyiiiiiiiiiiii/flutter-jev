import 'package:flutter/material.dart';

import '../data.dart';
import '../kit.dart';
import '../theme.dart';
import 'shell.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key});

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _remember = true;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _email.text.trim();
    if (email.isEmpty || _password.text.isEmpty) {
      setState(() => _error = 'Enter both an email and a password.');
      return;
    }
    if (!email.contains('@')) {
      setState(() => _error = 'That email address is not valid.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    await Future<void>.delayed(Store.instance.latency);
    if (!mounted) return;
    Store.instance.signIn(email);
    await Navigator.of(context)
        .pushReplacement(MaterialPageRoute(builder: (_) => const HomeShell()));
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: Tk.maxContent),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(Tk.xl, Tk.l, Tk.xl, Tk.xl),
              children: [
                const _Wordmark(),
                const SizedBox(height: Tk.xl),
                Container(
                  padding: const EdgeInsets.fromLTRB(Tk.l, Tk.l, Tk.l, Tk.l),
                  decoration: BoxDecoration(
                    color: Tk.brand,
                    borderRadius: BorderRadius.circular(Tk.radius),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your orders, sorted.',
                        style: text.headlineSmall?.copyWith(
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: Tk.xs),
                      Text(
                        'Follow a parcel, send something back, or ask us a question.',
                        style: text.bodyMedium?.copyWith(color: Tk.brandSoft),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: Tk.xl),
                identified(
                  Store.instance.k('email_field'),
                  TextField(
                    key: Key(Store.instance.k('email_field')),
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      prefixIcon: Icon(Icons.alternate_email, size: 19),
                    ),
                  ),
                ),
                const SizedBox(height: Tk.m),
                identified(
                  Store.instance.k('password_field'),
                  TextField(
                    key: Key(Store.instance.k('password_field')),
                    controller: _password,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: 'Password',
                      prefixIcon: Icon(Icons.lock_outline, size: 19),
                    ),
                  ),
                ),
                const SizedBox(height: Tk.s),
                identified(
                  'remember_me',
                  CheckboxListTile(
                    key: const Key('remember_me'),
                    value: _remember,
                    onChanged: (v) => setState(() => _remember = v ?? false),
                    title: const Text('Keep me signed in'),
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: Tk.s),
                  Container(
                    key: const Key('signin_error'),
                    padding: const EdgeInsets.all(Tk.m),
                    decoration: BoxDecoration(
                      color: Tk.dangerSoft,
                      borderRadius: BorderRadius.circular(Tk.radiusSm),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.error_outline,
                          size: 18,
                          color: Tk.danger,
                        ),
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
                  Store.instance.k('signin_button'),
                  FilledButton(
                    key: Key(Store.instance.k('signin_button')),
                    onPressed: _busy ? null : _submit,
                    child: _busy
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(Store.instance.label('Sign in')),
                  ),
                ),
                const SizedBox(height: Tk.s),
                identified(
                  'forgot_password_button',
                  TextButton(
                    key: const Key('forgot_password_button'),
                    onPressed: () => showModalBottomSheet<void>(
                      context: context,
                      showDragHandle: true,
                      builder: (_) => const _ResetSheet(),
                    ),
                    child: const Text('Forgot password?'),
                  ),
                ),
                const SizedBox(height: Tk.xl),
                Center(
                  child: Text(
                    'Demo build · any password works',
                    style: text.bodySmall,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// The brand mark: a parcel seen from above, the tape line in coral.
class _Wordmark extends StatelessWidget {
  const _Wordmark();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
            color: Tk.ink,
            borderRadius: BorderRadius.circular(5),
          ),
          alignment: Alignment.center,
          child: Container(width: 28, height: 5, color: Tk.warn),
        ),
        const SizedBox(width: Tk.s),
        Text(
          'Boxtide',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.4),
        ),
      ],
    );
  }
}

class _ResetSheet extends StatelessWidget {
  const _ResetSheet();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Tk.xl, 0, Tk.xl, Tk.xxl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Reset your password',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: Tk.s),
          Text(
            'We will send a link to the address on your account.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: Tk.l),
          identified(
            'reset_email_field',
            const TextField(
              key: Key('reset_email_field'),
              decoration: InputDecoration(labelText: 'Email'),
            ),
          ),
          const SizedBox(height: Tk.l),
          identified(
            'reset_send_button',
            FilledButton(
              key: const Key('reset_send_button'),
              onPressed: () {
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Reset link sent.'),
                    duration: Duration(seconds: 2),
                  ),
                );
              },
              child: const Text('Send reset link'),
            ),
          ),
        ],
      ),
    );
  }
}
