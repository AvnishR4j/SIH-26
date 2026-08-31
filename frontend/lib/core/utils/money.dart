class Money {
  const Money._();

  static int? rupeesTextToPaise(String value) {
    final rupees = double.tryParse(value.trim());
    if (rupees == null || rupees < 0) return null;
    return (rupees * 100).round();
  }

  static String formatPaise(int paise, {bool decimals = true}) {
    final rupees = paise / 100;
    return decimals ? '₹${rupees.toStringAsFixed(2)}' : '₹${rupees.round()}';
  }
}
