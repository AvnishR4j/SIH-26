import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.compact = false});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    final size = compact ? 38.0 : 52.0;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppColors.accent,
        borderRadius: BorderRadius.circular(compact ? 9 : 12),
      ),
      child: Icon(
        Icons.local_florist_outlined,
        color: Colors.white,
        size: compact ? 22 : 29,
      ),
    );
  }
}
