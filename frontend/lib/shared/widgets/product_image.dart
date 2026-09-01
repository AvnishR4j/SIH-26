import 'dart:io';

import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

class ProductImage extends StatelessWidget {
  const ProductImage({
    super.key,
    this.localPath,
    this.networkUrl,
    this.fit = BoxFit.cover,
    this.borderRadius = 8,
    this.preferNetwork = false,
    this.cacheWidth,
    this.cacheHeight,
  });

  final String? localPath;
  final String? networkUrl;
  final BoxFit fit;
  final double borderRadius;
  final bool preferNetwork;
  final int? cacheWidth;
  final int? cacheHeight;

  @override
  Widget build(BuildContext context) {
    final local = localPath;
    final network = networkUrl;
    final fallback = ColoredBox(
      color: AppColors.surface,
      child: const Center(
        child: Icon(Icons.image_outlined, color: AppColors.mutedText, size: 42),
      ),
    );
    Widget localImage() => local != null && File(local).existsSync()
        ? Image.file(
            File(local),
            fit: fit,
            cacheWidth: cacheWidth,
            cacheHeight: cacheHeight,
            errorBuilder: (_, _, _) => fallback,
          )
        : fallback;
    Widget networkImage() => network != null && network.isNotEmpty
        ? Image.network(
            network,
            fit: fit,
            cacheWidth: cacheWidth,
            cacheHeight: cacheHeight,
            errorBuilder: (_, _, _) => localImage(),
          )
        : localImage();
    Widget image;
    if (preferNetwork) {
      image = networkImage();
    } else if (local != null && File(local).existsSync()) {
      image = localImage();
    } else {
      image = networkImage();
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: image,
    );
  }
}
