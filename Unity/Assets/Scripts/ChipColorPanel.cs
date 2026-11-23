using System.Globalization;
using UnityEngine;
using UnityEngine.UI;

namespace Sitekick
{
	/// <summary>
	/// The colour field under the chip grid: type a hex value (no #) and Apply
	/// repaints the Sitekick and every chip effect that has a piece Flash would
	/// paint -- see <see cref="ChipEffect"/>.  An empty or unreadable value means
	/// white, which is the Sitekick's default colour, so Apply also undoes a colour.
	/// </summary>
	public class ChipColorPanel : MonoBehaviour
	{
		[SerializeField]
		protected ChipGallery gallery;

		[SerializeField]
		protected InputField field;

		[SerializeField]
		protected Button apply;

		protected void Awake()
		{
			if ( apply != null )
				apply.onClick.AddListener( ApplyField );
		}

		protected void Start()
		{
			if ( gallery != null )
				gallery.ApplyColor( gallery.EffectColor );
		}

		/// <summary>Reads the field and paints everything the colour reaches.</summary>
		public void ApplyField()
		{
			if ( gallery != null && field != null )
				gallery.ApplyColor( Parse( field.text ) );
		}

		/// <summary>The hex value the field is showing, for tools and tests.</summary>
		public string Hex { get { return field != null ? field.text : ""; } }

		/// <summary>
		/// Writes a value into the field without applying it, so the picker can
		/// keep the hex readout in step with the colour being dragged.
		/// </summary>
		public void SetHex( string hex )
		{
			if ( field != null && field.text != hex )
				field.text = hex;
		}

		/// <summary>Fills the field and presses Apply, for tools and tests.</summary>
		public void ApplyHex( string hex )
		{
			if ( field != null )
				field.text = hex;

			if ( apply != null )
				apply.onClick.Invoke();
			else if ( gallery != null )
				gallery.ApplyColor( Parse( hex ) );
		}

		/// <summary>`RRGGBB` or `RGB`, with or without a leading #; white when unreadable.</summary>
		public static Color Parse( string text )
		{
			text = ( text ?? "" ).Trim().TrimStart( '#' ).Trim();

			if ( text.Length == 3 )
				text = "" + text[0] + text[0] + text[1] + text[1] + text[2] + text[2];

			if ( text.Length != 6 ||
				!int.TryParse( text, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var value ) )
				return Color.white;

			return new Color( ( ( value >> 16 ) & 0xFF ) / 255f,
				( ( value >> 8 ) & 0xFF ) / 255f,
				( value & 0xFF ) / 255f, 1f );
		}
	}
}
