using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Sitekick
{
	/// <summary>
	/// A live colour picker for the gallery: drag inside the square for
	/// saturation and value, drag the strip for hue, and the Sitekick repaints
	/// under the pointer -- every drag step publishes a colour, so a chip effect
	/// already on show changes shade as the finger moves.
	///
	/// The picker is only a view of <see cref="SitekickColor"/>: whatever the
	/// hex field applies comes back through <see cref="SitekickColor.Changed"/>
	/// and moves the cursors, and a drag is just another publish.  It keeps hue
	/// and value itself while dragging (converting the published colour back to
	/// HSV would snap the hue at the grey ends of the square).
	/// </summary>
	public class ColorPicker : MonoBehaviour, IPointerDownHandler, IDragHandler, IPointerUpHandler
	{
		[SerializeField]
		protected ChipGallery gallery;

		/// <summary>Kept in step so the hex field always shows what is picked.</summary>
		[SerializeField]
		protected ChipColorPanel panel;

		[Tooltip( "Saturation/value square. Left is grey, right is the pure hue; bottom is black." )]
		[SerializeField]
		protected RectTransform area;

		[SerializeField]
		protected RectTransform areaCursor;

		[Tooltip( "Hue strip, left to right." )]
		[SerializeField]
		protected RectTransform hueBar;

		[SerializeField]
		protected RectTransform hueCursor;

		[SerializeField]
		protected Image swatch;

		[SerializeField]
		protected Text readout;

		const int AreaSize = 64;
		const int HueSize = 64;

		protected float hue;
		protected float saturation;
		protected float value = 1f;

		protected Texture2D areaTexture;
		protected Sprite areaSprite;
		protected Sprite hueSprite;
		protected Sprite ringSprite;

		protected bool dragging;
		protected int grabbing;   // 0 none, 1 the square, 2 the hue strip

		public RectTransform Area { get { return area; } }

		public RectTransform HueBar { get { return hueBar; } }

		public Color Color { get { return Color.HSVToRGB( hue, saturation, value ); } }

		protected void Awake()
		{
			BuildTextures();
			Refresh();
		}

		protected void OnEnable()
		{
			SitekickColor.Changed += Sync;
			Sync( SitekickColor.Current );
		}

		protected void OnDisable()
		{
			SitekickColor.Changed -= Sync;
		}

		/// <summary>Rebuilds the two gradient textures and the cursor rings.</summary>
		protected void BuildTextures()
		{
			areaTexture = new Texture2D( AreaSize, AreaSize, TextureFormat.RGBA32, false )
			{
				name = "Sitekick Colour Area",
				wrapMode = TextureWrapMode.Clamp,
				filterMode = FilterMode.Bilinear,
			};
			areaSprite = Sprite.Create( areaTexture, new Rect( 0, 0, AreaSize, AreaSize ), new Vector2( 0.5f, 0.5f ) );

			var hueTexture = new Texture2D( HueSize, 1, TextureFormat.RGBA32, false )
			{
				name = "Sitekick Colour Hue",
				wrapMode = TextureWrapMode.Clamp,
			};
			for ( var x = 0; x < HueSize; x++ )
				hueTexture.SetPixel( x, 0, Color.HSVToRGB( x / ( HueSize - 1f ), 1f, 1f ) );
			hueTexture.Apply();
			hueSprite = Sprite.Create( hueTexture, new Rect( 0, 0, HueSize, 1 ), new Vector2( 0.5f, 0.5f ) );

			ringSprite = MakeRing( 20, 3f );

			Show( area, areaSprite );
			Show( hueBar, hueSprite );
			ShowCursor( areaCursor, ringSprite );
			ShowCursor( hueCursor, ringSprite );
		}

		static void Show( RectTransform rect, Sprite sprite )
		{
			if ( rect != null && rect.TryGetComponent<Image>( out var image ) )
			{
				image.sprite = sprite;
				image.type = Image.Type.Simple;
				image.color = Color.white;
			}
		}

		static void ShowCursor( RectTransform rect, Sprite sprite )
		{
			if ( rect != null && rect.TryGetComponent<Image>( out var image ) )
			{
				image.sprite = sprite;
				image.color = Color.white;
				image.raycastTarget = false;
			}
		}

		/// <summary>A hollow white ring, so the cursor reads on any colour.</summary>
		static Sprite MakeRing( int size, float thickness )
		{
			var tex = new Texture2D( size, size, TextureFormat.RGBA32, false ) { wrapMode = TextureWrapMode.Clamp };
			var centre = ( size - 1 ) * 0.5f;
			for ( var y = 0; y < size; y++ )
			{
				for ( var x = 0; x < size; x++ )
				{
					var distance = Vector2.Distance( new Vector2( x, y ), new Vector2( centre, centre ) );
					var ring = distance <= centre - 0.5f && distance >= centre - thickness;
					tex.SetPixel( x, y, ring ? Color.white : Color.clear );
				}
			}

			tex.Apply();
			return Sprite.Create( tex, new Rect( 0, 0, size, size ), new Vector2( 0.5f, 0.5f ) );
		}

		/// <summary>Moves the cursors, repaints the square for the new hue, updates the readout.</summary>
		protected void Refresh()
		{
			PaintArea();

			if ( areaCursor != null )
			{
				areaCursor.anchorMin = areaCursor.anchorMax = new Vector2( saturation, value );
				areaCursor.anchoredPosition = Vector2.zero;
			}

			if ( hueCursor != null )
			{
				hueCursor.anchorMin = hueCursor.anchorMax = new Vector2( hue, 0.5f );
				hueCursor.anchoredPosition = Vector2.zero;
			}

			var color = Color;
			if ( swatch != null )
				swatch.color = color;
			if ( readout != null )
				readout.text = "#" + ColorUtility.ToHtmlStringRGB( color );
		}

		protected void PaintArea()
		{
			if ( areaTexture == null )
				return;

			for ( var y = 0; y < AreaSize; y++ )
			{
				for ( var x = 0; x < AreaSize; x++ )
					areaTexture.SetPixel( x, y, Color.HSVToRGB( hue, x / ( AreaSize - 1f ), y / ( AreaSize - 1f ) ) );
			}

			areaTexture.Apply( false );
		}

		/// <summary>Takes a colour from elsewhere (the hex field) without publishing it.</summary>
		protected void Sync( Color color )
		{
			if ( dragging )
				return;

			Color.RGBToHSV( color, out hue, out saturation, out value );
			Refresh();
		}

		public void OnPointerDown( PointerEventData eventData )
		{
			if ( area != null && RectTransformUtility.RectangleContainsScreenPoint( area, eventData.position, eventData.pressEventCamera ) )
				grabbing = 1;
			else if ( hueBar != null && RectTransformUtility.RectangleContainsScreenPoint( hueBar, eventData.position, eventData.pressEventCamera ) )
				grabbing = 2;
			else
				return;

			dragging = true;
			Drag( eventData.position, eventData.pressEventCamera );
		}

		public void OnDrag( PointerEventData eventData )
		{
			if ( dragging )
				Drag( eventData.position, eventData.pressEventCamera );
		}

		public void OnPointerUp( PointerEventData eventData )
		{
			dragging = false;
			grabbing = 0;
		}

		/// <summary>Reads the pointer into hue/ saturation/ value and publishes at once.</summary>
		protected void Drag( Vector2 screen, Camera camera )
		{
			if ( grabbing == 1 && Fraction( area, screen, camera, out var local ) )
			{
				saturation = local.x;
				value = local.y;
			}
			else if ( grabbing == 2 && Fraction( hueBar, screen, camera, out local ) )
			{
				hue = local.x;
			}
			else
			{
				return;
			}

			Refresh();
			Publish();
		}

		/// <summary>Where the pointer is inside a rect, 0..1 on each axis.</summary>
		protected static bool Fraction( RectTransform rect, Vector2 screen, Camera camera, out Vector2 fraction )
		{
			fraction = Vector2.zero;

			if ( rect == null || !RectTransformUtility.ScreenPointToLocalPointInRectangle( rect, screen, camera, out var local ) )
				return false;

			var bounds = rect.rect;
			fraction = new Vector2( Mathf.Clamp01( ( local.x - bounds.xMin ) / bounds.width ),
				Mathf.Clamp01( ( local.y - bounds.yMin ) / bounds.height ) );
			return true;
		}

		/// <summary>Hands the picked colour to the gallery; the hex field follows.</summary>
		protected void Publish()
		{
			var color = Color;

			if ( panel != null )
				panel.SetHex( ColorUtility.ToHtmlStringRGB( color ) );

			if ( gallery != null )
				gallery.ApplyColor( color );
			else
				SitekickColor.Set( color );
		}
	}
}
